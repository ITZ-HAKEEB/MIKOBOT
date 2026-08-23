from __future__ import annotations

import os
import ssl
import json
import asyncio
from typing import Optional, Dict, Any, List, Set

import redis
import pymongo
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv(
    "REDIS_URL",
    "rediss://:p98827a3f7f619e71f89933b124319976c83b7b5d99e28a15e01f48eea633a414@ec2-52-73-55-112.compute-1.amazonaws.com:32000",
)
MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb+srv://lily_music:Nishkarsh123@lilymusic.3bdrl7s.mongodb.net/?appName=lilymusic",
)

# Redis client
_redis_client: Optional[redis.Redis] = None
try:
    if REDIS_URL.startswith("rediss://"):
        _redis_client = redis.from_url(REDIS_URL, ssl_cert_reqs=None, decode_responses=True)
    else:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    _redis_client.ping()
    print("✅ Connected to Redis successfully!")
except Exception as e:
    print(f"⚠️ Redis connection warning: {e}")
    _redis_client = None

# Mongo client
_mongo_db: Optional[pymongo.database.Database] = None
try:
    _mongo_client = pymongo.MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    _mongo_db = _mongo_client.get_database("miko_bot")
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print(f"⚠️ MongoDB connection warning: {e}")
    _mongo_db = None


# --- CHATS & USERS TRACKING FOR BROADCAST ---

def add_chat(chat_id: int) -> None:
    cid = str(chat_id)
    if _redis_client:
        try:
            _redis_client.sadd("miko:chats", cid)
        except Exception:
            pass
    if _mongo_db is not None:
        try:
            _mongo_db.chats.update_one({"chat_id": cid}, {"$set": {"chat_id": cid}}, upsert=True)
        except Exception:
            pass


def rm_chat(chat_id: int) -> None:
    cid = str(chat_id)
    if _redis_client:
        try:
            _redis_client.srem("miko:chats", cid)
        except Exception:
            pass
    if _mongo_db is not None:
        try:
            _mongo_db.chats.delete_one({"chat_id": cid})
        except Exception:
            pass


def get_chats() -> List[int]:
    chats_set: Set[int] = set()
    if _redis_client:
        try:
            members = _redis_client.smembers("miko:chats")
            for m in members:
                chats_set.add(int(m))
        except Exception:
            pass
    if not chats_set and _mongo_db is not None:
        try:
            docs = _mongo_db.chats.find({}, {"chat_id": 1})
            for doc in docs:
                cid = doc.get("chat_id")
                if cid:
                    chats_set.add(int(cid))
                    if _redis_client:
                        _redis_client.sadd("miko:chats", str(cid))
        except Exception:
            pass
    return list(chats_set)


def add_user_chat(user_id: int) -> None:
    uid = str(user_id)
    if _redis_client:
        try:
            _redis_client.sadd("miko:users", uid)
        except Exception:
            pass
    if _mongo_db is not None:
        try:
            _mongo_db.users_chats.update_one({"user_id": uid}, {"$set": {"user_id": uid}}, upsert=True)
        except Exception:
            pass


def rm_user_chat(user_id: int) -> None:
    uid = str(user_id)
    if _redis_client:
        try:
            _redis_client.srem("miko:users", uid)
        except Exception:
            pass
    if _mongo_db is not None:
        try:
            _mongo_db.users_chats.delete_one({"user_id": uid})
        except Exception:
            pass


def get_user_chats() -> List[int]:
    users_set: Set[int] = set()
    if _redis_client:
        try:
            members = _redis_client.smembers("miko:users")
            for m in members:
                users_set.add(int(m))
        except Exception:
            pass
    if not users_set and _mongo_db is not None:
        try:
            docs = _mongo_db.users_chats.find({}, {"user_id": 1})
            for doc in docs:
                uid = doc.get("user_id")
                if uid:
                    users_set.add(int(uid))
                    if _redis_client:
                        _redis_client.sadd("miko:users", str(uid))
        except Exception:
            pass
    return list(users_set)


# --- USER DATA DUAL LAYER ---

def db_load_user(user_id: int) -> Optional[Dict[str, Any]]:
    uid = str(user_id)
    # 1. Try Redis
    if _redis_client:
        try:
            val = _redis_client.get(f"miko:user:{uid}")
            if val:
                return json.loads(val)
        except Exception:
            pass

    # 2. Try Mongo
    if _mongo_db is not None:
        try:
            doc = _mongo_db.users.find_one({"_id": uid})
            if doc:
                doc.pop("_id", None)
                if _redis_client:
                    _redis_client.set(f"miko:user:{uid}", json.dumps(doc), ex=86400)
                return doc
        except Exception:
            pass

    return None


def db_save_user(user_id: int, udata: Dict[str, Any]) -> None:
    uid = str(user_id)
    serialized = json.dumps(udata)

    # 1. Save to Redis
    if _redis_client:
        try:
            _redis_client.set(f"miko:user:{uid}", serialized, ex=86400)
        except Exception:
            pass

    # 2. Save to Mongo
    if _mongo_db is not None:
        try:
            doc = dict(udata)
            _mongo_db.users.update_one({"_id": uid}, {"$set": doc}, upsert=True)
        except Exception:
            pass


def db_load_all_users() -> Dict[str, Dict[str, Any]]:
    res: Dict[str, Dict[str, Any]] = {}
    if _mongo_db is not None:
        try:
            for doc in _mongo_db.users.find({}):
                uid = doc.pop("_id", None)
                if uid:
                    res[str(uid)] = doc
        except Exception:
            pass
    return res
