from pymongo import MongoClient
import os
import asyncio
import motor.motor_asyncio
from dotenv import load_dotenv
#load envs
load_dotenv()

#get envs
MONGODB_URI = os.getenv("MONGODB_URI")
TEST_DB_NAME = os.getenv("TEST_DB_NAME")
DEV_DB_NAME = os.getenv("DEV_DB_NAME")
PROD_DB_NAME = os.getenv("PROD_DB_NAME")

#create client (update to have both sync and async)

# this function is used to check if there's an active event loop

def is_asyncio_mode(): # added this function to handle asyncio event loop
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
        return asyncio.get_event_loop()


# Using either sync or async client 
if not is_asyncio_mode():
    client = MongoClient(MONGODB_URI)
    print("Using AsyncIOMotorClient (asynchronous mode).")
else:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    print("Using AsyncIOMotorClient (asynchronous mode).")

#current database
database = client[TEST_DB_NAME]

#collections
user_accounts = database["user_accounts"]

