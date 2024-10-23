from datetime import datetime
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field


# MongoDB Models (NoSQL Database)

class MongoUser(Document):
    username: str
    email: str
    hashed_password: str
    balance: float = 0.0
    is_active: bool = True

    class Settings:
        collection = "users"


class MongoTradingPair(Document):
    symbol: str = Field(..., description="Trading pair symbol, e.g., BTC, ETH")
    price: float = Field(..., description="Latest price of the trading pair")

    class Settings:
        collection = "trading_pairs"


class MongoOrder(Document):
    user_id: PydanticObjectId
    symbol: str  # Currency pair symbol
    amount: float  # Bet amount
    prediction: str  # 'rise' or 'fall'
    trade_time: int  # Trade duration in seconds
    start_time: datetime = Field(default_factory=datetime.utcnow)   # Time when the order was placed
    locked_price: float  # Price at the time the order was placed
    status: str = 'pending'  # Status: 'pending', 'win', 'lose'
    payout: Optional[float] = None   # Payout for the order (if won)

    class Settings:
        collection = "orders"
