import asyncio
import json
import logging
import time
from typing import List, Optional, Dict, Set

from bson import timestamp
from fastapi.middleware.cors import CORSMiddleware
import websockets
from beanie import init_beanie
from cachetools import TTLCache
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from websockets.exceptions import ConnectionClosed, ConnectionClosedError
import os
# connect to MongoDB
from connect import connect_to_mongodb
from db_config import MONGODB_URI, TEST_DB_NAME
from model import MongoTradingPair

# Initialize MongoDB client and Beanie ODM
client = AsyncIOMotorClient(MONGODB_URI)
db = client[TEST_DB_NAME]

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

connect_to_mongodb()
# Import your MongoTradingPair model for DB operations

# WebSocket URLs for different sources
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
KRAKEN_WS_URL = "wss://ws.kraken.com"

# Mapping of symbols to internal representation
WEBSOCKET_CURRENCY_PAIRS = {
    # Binance pairs
    "btcusdt": "BTC",
    "ethusdt": "ETH",
    "ltcusdt": "LTC",
    "bnbusdt": "BNB",
    "xrpusdt": "XRP",
    "adausdt": "ADA",
    "dogeusdt": "DOGE",
    "solusdt": "SOL",
    "dotusdt": "DOT",
    "linkusdt": "LINK",
    "uniusdt": "UNI",
    "oaxusdt": "OAX",
    "arbusdt": "ARB",
    "usdtron": "USDTRON",

    # Kraken pairs
    "XBT/USD": "BTC",
    "ETH/USD": "ETH",
    "LTC/USD": "LTC",
    "XRP/USD": "XRP",
    "ADA/USD": "ADA",
    "DOGE/USD": "DOGE",
    "SOL/USD": "SOL",
    "DOT/USD": "DOT",
    "LINK/USD": "LINK",
    "UNI/USD": "UNI",

    # Forex pairs
    "EUR/USD": "EUR/USD",
    "GBP/USD": "GBP/USD",
    "USD/JPY": "USD/JPY",
    "USD/CHF": "USD/CHF",
    "AUD/USD": "AUD/USD",
    "USD/CAD": "USD/CAD",
    "EUR/GBP": "EUR/GBP",
    "EUR/JPY": "EUR/JPY",

    # Additional currencies
    "USD/KSH": "KES",
    "USD/UGX": "UGX",

    # Alternative spellings
    "eurusd": "EUR/USD",
    "usdjpy": "USD/JPY",
    "usdchf": "USD/CHF",
    "gbpusd": "GBP/USD",
    "audusd": "AUD/USD",
    "usdcad": "USD/CAD",
    "usdksh": "USD/KES",
}

# FastAPI app initialization
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your actual frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from the "static" directory

# Get the absolute path to the static directory
static_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "static")
print(f"Serving static files from: {static_dir}")  # Debug to check the path

# Create the static directory if it doesn't exist
os.makedirs(static_dir, exist_ok=True)

# Mount the static directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# TTLCache Configuration for price caching
price_cache = TTLCache(maxsize=10000, ttl=30)
last_update_times = TTLCache(maxsize=10000, ttl=2)  # Store last update times with a short TTL of 2 seconds
latest_prices = {}
latest_prices_lock = asyncio.Lock()
latest_data_lock = asyncio.Lock()
latest_timestamps = {}
latest_ranks = {}


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # symbol -> set of WebSockets
        self.all_assets_connections: Set[WebSocket] = set()  # WebSockets subscribed to all assets
        self.connection_symbols: Dict[WebSocket, Set[str]] = {}  # WebSocket -> set of symbols

    async def connect(self, websocket: WebSocket, symbols: Optional[List[str]] = None):
        await websocket.accept()
        if symbols is None or "ALL" in symbols:
            self.all_assets_connections.add(websocket)
            self.connection_symbols[websocket] = set(latest_prices.keys())
        else:
            self.connection_symbols[websocket] = set(symbols)
            for symbol in symbols:
                if symbol not in self.active_connections:
                    self.active_connections[symbol] = set()
                self.active_connections[symbol].add(websocket)

    def disconnect(self, websocket: WebSocket):
        symbols = self.connection_symbols.get(websocket, set())
        for symbol in symbols:
            if symbol in self.active_connections:
                self.active_connections[symbol].discard(websocket)
                if not self.active_connections[symbol]:
                    del self.active_connections[symbol]
        self.all_assets_connections.discard(websocket)
        self.connection_symbols.pop(websocket, None)

    async def broadcast_to_symbol(self, symbol: str, message: str):
        connections = self.active_connections.get(symbol, set()).union(self.all_assets_connections)
        disconnected = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(connection)

# Initialize connection manager
manager = ConnectionManager()

# WebSocket route to handle price updates

@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    await websocket.accept()
    await manager.connect(websocket)

    try:
        # Send initial prices when the client connects
        async with latest_prices_lock:
            if latest_prices:
                for symbol, price in latest_prices.items():
                    await websocket.send_text(json.dumps({symbol: price}))

        # Keep connection alive by sending regular updates or pings
        while True:
            try:
                # Send periodic price updates or pings to keep connection alive
                async with latest_prices_lock:
                    if latest_prices:
                        for symbol, price in latest_prices.items():
                            await websocket.send_text(json.dumps({symbol: price}))
                    else:
                        # Send a ping message if no prices are available to keep the connection alive
                        await websocket.send_text(json.dumps({"type": "ping"}))
                await asyncio.sleep(5)  # Send updates every 5 seconds
            except WebSocketDisconnect:
                manager.disconnect(websocket)
                break
    except Exception as e:
        logger.error(f"Error in websocket connection: {e}")
        manager.disconnect(websocket)



# WebSocket route to handle price updates and specific symbols
@app.websocket("/ws/market/{symbols}")
async def websocket_market_data(websocket: WebSocket, symbols: str):
    try:
        # Parse symbols and handle potential parsing errors
        try:
            requested_symbols = [s.strip().upper() for s in symbols.split(',')]
            subscribe_all = "ALL" in requested_symbols
        except Exception as e:
            logger.error(f"Error parsing symbols: {e}")
            await websocket.close(code=1008, reason="Invalid symbol format.")
            return

        # Connect to WebSocket manager, catching any potential connection errors
        try:
            await manager.connect(websocket, requested_symbols if not subscribe_all else None)
        except Exception as e:
            logger.error(f"Connection error during WebSocket setup: {e}")
            await websocket.close(code=1011, reason="Connection setup failed.")
            return

        # Prepare initial data to send to client
        initial_prices = {}
        initial_ranks = {}
        initial_timestamps = {}

        try:
            async with latest_data_lock:
                if subscribe_all:
                    initial_prices = latest_prices.copy()
                    initial_ranks = latest_ranks.copy()
                    initial_timestamps = latest_timestamps.copy()
                else:
                    for symbol in requested_symbols:
                        if symbol in latest_prices:
                            initial_prices[symbol] = latest_prices[symbol]
                            initial_ranks[symbol] = latest_ranks.get(symbol, None)
                            initial_timestamps[symbol] = latest_timestamps.get(symbol, None)
        except Exception as e:
            logger.error(f"Error retrieving initial data: {e}")
            await websocket.close(code=1011, reason="Error retrieving initial data.")
            return

        # Send initial data and handle potential transmission errors
        try:
            await websocket.send_text(json.dumps({
                "type": "initial",
                "data": initial_prices,
                "ranks": initial_ranks,
                "timestamps": initial_timestamps
            }))
        except Exception as e:
            logger.error(f"Error sending initial data to WebSocket client: {e}")
            await websocket.close(code=1011, reason="Error sending initial data.")
            return

        # Listen for client messages
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"Received message from client: {data}")
                # Optional: Handle messages from client if needed
            except WebSocketDisconnect:
                logger.info("Client disconnected.")
                manager.disconnect(websocket)
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON format received: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format."
                }))
            except Exception as e:
                logger.error(f"Unexpected error receiving message from client: {e}")
                await websocket.close(code=1011, reason="Unexpected error in message handling.")
                break
    except Exception as e:
        logger.error(f"Unhandled WebSocket error: {e}")
        if not websocket.client_state.disconnected:
            await websocket.close(code=1011, reason="Internal server error.")


# Helper functions for WebSocket subscription messages
def get_kraken_subscription_message():
    pairs = [
        "XBT/USD", "ETH/USD", "LTC/USD", "XRP/USD", "ADA/USD",
        "DOGE/USD", "SOL/USD", "DOT/USD", "LINK/USD", "UNI/USD",
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD",
        "USD/CAD", "EUR/GBP", "EUR/JPY", "USD/KES", "USD/UGX"
    ]
    return json.dumps({
        "event": "subscribe",
        "pair": pairs,
        "subscription": {
            "name": "ticker"
        }
    })



def get_binance_subscription_message():
    symbols = [
        "btcusdt", "ethusdt", "ltcusdt", "bnbusdt", "xrpusdt",
        "adausdt", "dogeusdt", "solusdt", "dotusdt", "linkusdt",
        "uniusdt", "oaxusdt", "arbusdt", "usdtron@trade"
    ]
    params = [f"{symbol}@trade" for symbol in symbols]
    return json.dumps({
        "method": "SUBSCRIBE",
        "params": params,
        "id": 1
    })


async def send_pings(websocket, interval=10):
    while True:
        await asyncio.sleep(interval)
        try:
            pong_waiter = await websocket.ping()
            await asyncio.wait_for(pong_waiter, timeout=10)  # Wait for the pong message with a timeout
            logger.info("Ping successful!")
        except asyncio.TimeoutError:
            logger.error("Ping timed out. Connection might be unstable.")
            break
        except Exception as e:
            logger.error(f"Failed to send ping: {e}")
            break

# Function to check if prices should be updated (throttling)
async def should_update(symbol: str, interval: int = 2):
    current_time = time.time()
    last_update_time = last_update_times.get(symbol, 0)
    if last_update_time is None or current_time - last_update_time >= interval:
        last_update_times[symbol] = current_time
        return True
    return False

def calculate_ranks():
    price_list = sorted(latest_prices.items(), key=lambda x: x[1], reverse=True)
    rank_dict = {symbol: rank + 1 for rank, (symbol, _) in enumerate(price_list)}
    return rank_dict

# Function to handle incoming messages from WebSockets (Binance & Kraken)
async def handle_message(message):
    try:
        # Log the incoming message for inspection
        logger.info(f"Received message: {message}")
        data = json.loads(message)
        # print(data)

        # Handle Binance messages
        if isinstance(data, dict) and data.get("e") == "trade":
            symbol = data["s"].lower()
            price = float(data["p"])
            timestamp = int(float(data['T']) / 1000)  # Unix timestamp in seconds
            if symbol in WEBSOCKET_CURRENCY_PAIRS:
                mapped_symbol = WEBSOCKET_CURRENCY_PAIRS[symbol]
                if await should_update(mapped_symbol):
                    async with latest_prices_lock:
                        latest_prices[mapped_symbol] = price
                        latest_timestamps[mapped_symbol] = timestamp
                        latest_ranks.update(calculate_ranks())

                    # Broadcast price update to WebSocket clients
                    # update_message = json.dumps({mapped_symbol: price})
                    # await manager.broadcast(update_message)

                    # Use the new broadcast method
                    update_message = json.dumps({
                        "type": "update",
                        "symbol": mapped_symbol,
                        "price": price,
                        "rank": latest_ranks[mapped_symbol],
                        "timestamp": timestamp
                    })

                    # Broadcast the update
                    await manager.broadcast_to_symbol(mapped_symbol, update_message)
                    await update_or_create_trading_pair(mapped_symbol, price)

        # Handle Kraken messages
        elif isinstance(data, list) and len(data) > 1 and isinstance(data[1], dict):
            pair = data[3]
            price = float(data[1]['c'][0])
            mapped_symbol = WEBSOCKET_CURRENCY_PAIRS.get(pair)
            timestamp = int(time.time() * 1000)  # Use current time in milliseconds
            if mapped_symbol:
                if await should_update(mapped_symbol):
                    async with latest_prices_lock:
                        latest_prices[mapped_symbol] = price
                        latest_timestamps[mapped_symbol] = timestamp
                        latest_ranks.update(calculate_ranks())

                    # Broadcast price update to WebSocket clients
                    # update_message = json.dumps({mapped_symbol: price})
                    # await manager.broadcast(update_message)

                    # Prepare the update message
                    update_message = json.dumps({
                        "type": "update",
                        "symbol": mapped_symbol,
                        "price": price,
                        "rank": latest_ranks[mapped_symbol],
                        "timestamp": timestamp
                    })

                    await manager.broadcast_to_symbol(mapped_symbol, update_message)
                    await update_or_create_trading_pair(mapped_symbol, price)

    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")


# MongoDB update or create trading pair function
async def update_or_create_trading_pair(symbol: str, price: float):
    try:
        symbol = symbol.upper()  # Ensure uniform case for symbol
        logger.info(f"Processing trading pair: {symbol} with price: {price}")

        # Print or log the price and symbol before querying MongoDB
        print(f"Updating or creating trading pair {symbol} with price {price}")

        mongo_trading_pair = await MongoTradingPair.find_one(MongoTradingPair.symbol == symbol)

        if mongo_trading_pair:
            logger.info(f"Found existing trading pair: {symbol}, updating price to {price}")
            mongo_trading_pair.price = price
            mongo_trading_pair.timestamp = timestamp
            await mongo_trading_pair.save()
        else:
            logger.info(f"Creating new trading pair: {symbol} with price {price}")
            mongo_trading_pair = MongoTradingPair(symbol=symbol, price=price, timestamp=timestamp)
            await mongo_trading_pair.insert()
        logger.info(f"Updated/created trading pair {symbol} with price {price}.")

    except Exception as e:
        logger.error(f"Failed to update or create trading pair {symbol}: {e}")
        print(f"Failed to update or create trading pair {symbol}: {e}")


# WebSocket listeners for Binance and Kraken
async def binance_websocket_listener():
    await reconnect_with_backoff(BINANCE_WS_URL, get_binance_subscription_message())


async def kraken_websocket_listener():
    await reconnect_with_backoff(KRAKEN_WS_URL, get_kraken_subscription_message())


# Reconnect to WebSocket with exponential backoff
async def reconnect_with_backoff(url, subscription_message):
    delay = 2
    max_delay = 15
    while True:
        try:
            websocket = await websockets.connect(url, ping_interval=150, ping_timeout=10)
            logger.info(f"Connected to WebSocket at {url}.")
            await websocket.send(subscription_message)
            asyncio.create_task(send_pings(websocket, interval=15))
            while True:
                message = await websocket.recv()
                await handle_message(message)
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"Connection closed: {e}. Retrying in {delay} seconds.")
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)
        except Exception as e:
            logger.error(f"Failed to connect: {e}. Retrying in {delay} seconds.")
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)


# Start both Binance and Kraken listeners
async def fetch_real_time_prices():
    await asyncio.gather(
        binance_websocket_listener(),
        kraken_websocket_listener()
    )


@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Initializing MongoDB with Beanie...")
        await init_beanie(database=db, document_models=[MongoTradingPair])
        logger.info("MongoDB initialization successful!")
        print("MongoDB initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {e}")
        print(f"Error initializing MongoDB: {e}")
        raise e

    # Start the background task for fetching real-time prices
    asyncio.create_task(start_price_fetching_task())

async def start_price_fetching_task():
    while True:
        try:
            # Fetch real-time prices
            await fetch_real_time_prices()
        except (ConnectionClosed, ConnectionClosedError) as e:
            logger.error(f"WebSocket connection error: {e}. Reconnecting in 5 seconds...")
            print(f"WebSocket connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)  # Wait before attempting reconnection
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
            print(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)  # Wait before attempting reconnection

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
