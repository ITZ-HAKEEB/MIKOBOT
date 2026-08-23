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


def get_redis_client() -> Optional[redis.Redis]:
    return _redis_client


def get_mongo_db() -> Optional[pymongo.database.Database]:
    return _mongo_db


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


from concurrent.futures import ThreadPoolExecutor

_db_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="miko_db_sync")


def _async_mongo_save_user(uid: str, doc: dict):
    if _mongo_db is not None:
        try:
            _mongo_db.users.update_one({"_id": uid}, {"$set": doc}, upsert=True)
        except Exception:
            pass


def db_save_user(user_id: int, udata: Dict[str, Any]) -> None:
    uid = str(user_id)
    serialized = json.dumps(udata)

    # 1. Save to Redis (instant in-memory write < 0.5ms)
    if _redis_client:
        try:
            _redis_client.set(f"miko:user:{uid}", serialized, ex=86400 * 7)
        except Exception:
            pass

    # 2. Async background sync to Mongo (zero command lag)
    doc = dict(udata)
    _db_pool.submit(_async_mongo_save_user, uid, doc)


def warmup_redis_cache() -> None:
    """Pre-warm Redis with all collections from MongoDB asynchronously."""
    if not _redis_client or _mongo_db is None:
        return
    try:
        collections = _mongo_db.list_collection_names()
        pipe = _redis_client.pipeline()
        for coll_name in collections:
            for doc in _mongo_db[coll_name].find({}):
                doc_id = str(doc.pop("_id", None))
                if not doc_id:
                    continue
                if coll_name == "users":
                    pipe.set(f"miko:user:{doc_id}", json.dumps(doc), ex=86400 * 7)
                    pipe.sadd("miko:users", doc_id)
                elif coll_name == "chats":
                    pipe.sadd("miko:chats", doc_id)
                elif coll_name == "users_chats":
                    pipe.sadd("miko:users", doc_id)
                elif coll_name == "sudoers":
                    pipe.sadd("miko:sudoers", doc_id)
                else:
                    pipe.set(f"miko:{coll_name}:{doc_id}", json.dumps(doc))
        pipe.execute()
        print("⚡ Redis in-memory cache pre-warmed successfully from MongoDB!")
    except Exception as e:
        print(f"⚠️ Redis warm-up notice: {e}")


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


# --- SUDOERS DUAL LAYER ---

DEFAULT_SUDOERS = {7408854697, 6605051662, 5971488185, 7810795240}


def get_owner_id() -> int:
    env_owner = os.getenv("OWNER_ID")
    if env_owner and env_owner.isdigit():
        return int(env_owner)
    return 7408854697


def add_sudo_user(user_id: int) -> None:
    uid = str(user_id)
    if _redis_client:
        try:
            _redis_client.sadd("miko:sudoers", uid)
        except Exception:
            pass
    if _mongo_db is not None:
        try:
            _mongo_db.sudoers.update_one({"user_id": uid}, {"$set": {"user_id": uid}}, upsert=True)
        except Exception:
            pass


def rm_sudo_user(user_id: int) -> None:
    uid = str(user_id)
    if _redis_client:
        try:
            _redis_client.srem("miko:sudoers", uid)
        except Exception:
            pass
    if _mongo_db is not None:
        try:
            _mongo_db.sudoers.delete_one({"user_id": uid})
        except Exception:
            pass


def get_sudo_users() -> List[int]:
    sudos: Set[int] = set(DEFAULT_SUDOERS)
    sudos.add(get_owner_id())
    if _redis_client:
        try:
            members = _redis_client.smembers("miko:sudoers")
            for m in members:
                sudos.add(int(m))
        except Exception:
            pass
    if _mongo_db is not None:
        try:
            docs = _mongo_db.sudoers.find({}, {"user_id": 1})
            for doc in docs:
                uid = doc.get("user_id")
                if uid:
                    sudos.add(int(uid))
        except Exception:
            pass
    return list(sudos)


def is_sudo_user(user_id: int) -> bool:
    if user_id == get_owner_id() or user_id in DEFAULT_SUDOERS:
        return True
    return user_id in get_sudo_users()


# --- GROUP SETTINGS DUAL LAYER ---

def db_load_group(chat_id: int) -> Optional[Dict[str, Any]]:
    cid = str(chat_id)
    if _redis_client:
        try:
            val = _redis_client.get(f"miko:group:{cid}")
            if val:
                return json.loads(val)
        except Exception:
            pass
    if _mongo_db is not None:
        try:
            doc = _mongo_db.groups.find_one({"_id": cid})
            if doc:
                doc.pop("_id", None)
                if _redis_client:
                    _redis_client.set(f"miko:group:{cid}", json.dumps(doc), ex=86400)
                return doc
        except Exception:
            pass
    return None


def _async_mongo_save_group(cid: str, doc: dict):
    if _mongo_db is not None:
        try:
            _mongo_db.groups.update_one({"_id": cid}, {"$set": doc}, upsert=True)
        except Exception:
            pass


def db_save_group(chat_id: int, gdata: Dict[str, Any]) -> None:
    cid = str(chat_id)
    serialized = json.dumps(gdata)
    # 1. Save to Redis immediately (< 0.5ms)
    if _redis_client:
        try:
            _redis_client.set(f"miko:group:{cid}", serialized, ex=86400 * 7)
        except Exception:
            pass
    # 2. Save to Mongo in background
    doc = dict(gdata)
    _db_pool.submit(_async_mongo_save_group, cid, doc)


