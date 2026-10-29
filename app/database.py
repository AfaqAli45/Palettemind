import os
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ServerSelectionTimeoutError


MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGO_DB_NAME", "color_palette_db")

try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=3000
    )
    client.server_info()

    db = client[DB_NAME]

    users_collection = db["users"]
    likes_collection = db["likes"]
    dislikes_collection = db["dislikes"]
    palettes_collection = db["palettes"]

    users_collection.create_index([("email", ASCENDING)], unique=True)
    likes_collection.create_index([("user_id", ASCENDING), ("palette_hash", ASCENDING)], unique=True)
    dislikes_collection.create_index([("user_id", ASCENDING), ("palette_hash", ASCENDING)], unique=True)
    palettes_collection.create_index([("created_at", ASCENDING)])

    print("✅ MongoDB Connected Successfully")

except ServerSelectionTimeoutError as e:
    print("❌ MongoDB Connection Failed:", e)
    users_collection = None
    likes_collection = None
    dislikes_collection = None
    palettes_collection = None
