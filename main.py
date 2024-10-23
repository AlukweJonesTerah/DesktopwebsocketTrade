import asyncio
import json
import logging
import time
from typing import List, Optional, Dict
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

connect_to_mongodb()
# Import your MongoTradingPair model for DB operations

# WebSocket URLs for different sources
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
KRAKEN_WS_URL = "wss://ws.kraken.com"

# Mapping of symbols to internal representation
WEBSOCKET_CURRENCY_PAIRS = {
    "btcusdt": "BTC",
    "ethusdt": "ETH",
    "ltcusdt": "LTC",
    "bnbusdt": "BNB",
    "xrpusdt": "XRP",
    "XBT/USD": "BTC",
    "ETH/USD": "ETH",
    "USD/KSH": "KES",
    "USD/UGX": "UGX",
    "EUR/USD": "USD",
    "USD/JPY": "JPY",
    "eurusd": "EUR/USD",
    "usdgbp": "USD/GBP",
    "usdjpy": "USD/JPY",
    "usdchf": "USD/CHF",
    "usdksh": "USD/KES"
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


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.connection_symbols: Dict[WebSocket, set] = {}

    async def connect(self, websocket: WebSocket, symbols: Optional[List[str]] = None):
        await websocket.accept()
        if symbols is None:
            symbols = list(WEBSOCKET_CURRENCY_PAIRS.values())

        # Store which symbols this connection is interested in
        self.connection_symbols[websocket] = set(symbols)

        # Add the connection to each symbol's list
        for symbol in symbols:
            if symbol not in self.active_connections:
                self.active_connections[symbol] = []
            self.active_connections[symbol].append(websocket)

    def disconnect(self, websocket: WebSocket):
        # Remove from symbol-specific connections
        symbols = self.connection_symbols.get(websocket, set())
        for symbol in symbols:
            if symbol in self.active_connections:
                if websocket in self.active_connections[symbol]:
                    self.active_connections[symbol].remove(websocket)

                # Clean up empty symbol lists
                if not self.active_connections[symbol]:
                    del self.active_connections[symbol]

        # Remove from connection symbols mapping
        if websocket in self.connection_symbols:
            del self.connection_symbols[websocket]

    async def broadcast_to_symbol(self, symbol: str, message: str):
        if symbol in self.active_connections:
            disconnected = []
            for connection in self.active_connections[symbol]:
                try:
                    await connection.send_text(message)
                except WebSocketDisconnect:
                    disconnected.append(connection)
                except Exception as e:
                    logging.error(f"Error broadcasting to connection: {e}")
                    disconnected.append(connection)

            # Clean up any disconnected clients
            for connection in disconnected:
                self.disconnect(connection)


# Initialize connection manager
manager = ConnectionManager()

logger = logging.getLogger(__name__)


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
        # Parse the symbols from the URL
        requested_symbols = [s.strip().upper() for s in symbols.split(',')]

        # Validate symbols
        valid_symbols = set(WEBSOCKET_CURRENCY_PAIRS.values())
        invalid_symbols = [s for s in requested_symbols if s not in valid_symbols]
        if invalid_symbols:
            await websocket.close(code=1008, reason=f"Invalid symbols: {','.join(invalid_symbols)}")
            return

        # Connect the WebSocket with specified symbols
        await manager.connect(websocket, requested_symbols)

        # Send initial prices for requested symbols
        initial_prices = {}
        async with latest_prices_lock:
            for symbol in requested_symbols:
                if symbol in latest_prices:
                    initial_prices[symbol] = latest_prices[symbol]

        if initial_prices:
            await websocket.send_text(json.dumps({
                "type": "initial",
                "data": initial_prices
            }))

        # Keep the connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any client messages here if needed
                try:
                    message = json.loads(data)
                    # You can add custom message handling here
                    await websocket.send_text(json.dumps({
                        "type": "acknowledgment",
                        "message": "Message received"
                    }))
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
            except WebSocketDisconnect:
                manager.disconnect(websocket)
                break
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        if not websocket.client_state.disconnected:
            await websocket.close(code=1011, reason="Internal server error")
        raise



# Helper functions for WebSocket subscription messages
def get_kraken_subscription_message():
    return json.dumps({
        "event": "subscribe",
        "pair": ["XBT/USD", "ETH/USD", "BTC/USD", "USD/KES", "USD/JPY", "EUR/USD", "USD/UGX"],
        "subscription": {
            "name": "ticker"
        }
    })


def get_binance_subscription_message():
    return json.dumps({
        "method": "SUBSCRIBE",
        "params": [
            "btcusdt@trade",
            "ethusdt@trade",
            "ltcusdt@trade",
            "bnbusdt@trade",
            "xrpusdt@trade"
        ],
        "id": 1
    })

async def send_pings(websocket, interval=30):
    while True:
        await asyncio.sleep(interval)
        try:
            pong_waiter = await websocket.ping()
            await asyncio.wait_for(pong_waiter, timeout=30)  # Wait for the pong message with a timeout
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
            if symbol in WEBSOCKET_CURRENCY_PAIRS:
                mapped_symbol = WEBSOCKET_CURRENCY_PAIRS[symbol]
                if await should_update(mapped_symbol):
                    async with latest_prices_lock:
                        latest_prices[mapped_symbol] = price

                    # Broadcast price update to WebSocket clients
                    # update_message = json.dumps({mapped_symbol: price})
                    # await manager.broadcast(update_message)

                    # Use the new broadcast method
                    update_message = json.dumps({
                        "type": "update",
                        "symbol": mapped_symbol,
                        "price": price,
                        "timestamp": int(time.time() * 1000)
                    })
                    await manager.broadcast_to_symbol(mapped_symbol, update_message)
                    await update_or_create_trading_pair(mapped_symbol, price)

        # Handle Kraken messages
        elif isinstance(data, list) and len(data) > 1 and isinstance(data[1], dict):
            pair = data[3]
            price = float(data[1]['c'][0])
            mapped_symbol = WEBSOCKET_CURRENCY_PAIRS.get(pair)
            if mapped_symbol:
                if await should_update(mapped_symbol):
                    async with latest_prices_lock:
                        latest_prices[mapped_symbol] = price

                    # Broadcast price update to WebSocket clients
                    # update_message = json.dumps({mapped_symbol: price})
                    # await manager.broadcast(update_message)
                    update_message = json.dumps({
                        "type": "update",
                        "symbol": mapped_symbol,
                        "price": price,
                        "timestamp": int(time.time() * 1000)
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
            await mongo_trading_pair.save()
        else:
            logger.info(f"Creating new trading pair: {symbol} with price {price}")
            mongo_trading_pair = MongoTradingPair(symbol=symbol, price=price)
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
    max_delay = 60
    while True:
        try:
            websocket = await websockets.connect(url, ping_interval=500, ping_timeout=30)
            logger.info(f"Connected to WebSocket at {url}.")
            await websocket.send(subscription_message)
            asyncio.create_task(send_pings(websocket, interval=120))
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
