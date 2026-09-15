import os
import json
import redis
import pymongo
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv(
    "REDIS_URL",
    "rediss://:pd5c00029f6c1c29ede4dd8c868cd594d149a84816fc103e47d7aa6c02ed24a23@ec2-184-193-54-112.compute-1.amazonaws.com:12950",
)
MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb+srv://lily_music:Nishkarsh123@lilymusic.3bdrl7s.mongodb.net/?appName=lilymusic",
)

def run_sync():
    print("🔌 Connecting to Redis...")
    if REDIS_URL.startswith("rediss://"):
        r = redis.from_url(REDIS_URL, ssl_cert_reqs=None, decode_responses=True)
    else:
        r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    print("✅ Redis Connected!")

    print("🔌 Connecting to MongoDB...")
    client = pymongo.MongoClient(MONGO_URL, serverSelectionTimeoutMS=8000)
    db = client.get_database("miko_bot")
    print(f"✅ MongoDB Connected! Database: {db.name}")

    collections = db.list_collection_names()
    print(f"📦 Collections found in Mongo: {collections}")

    summary = {}

    # 1. Sync Users
    if "users" in collections:
        users = list(db.users.find({}))
        print(f"👤 Found {len(users)} users in MongoDB.")
        user_count = 0
        pipe = r.pipeline()
        for doc in users:
            uid = str(doc.pop("_id", None))
            if uid:
                pipe.set(f"miko:user:{uid}", json.dumps(doc))
                pipe.sadd("miko:users", uid)
                user_count += 1
        pipe.execute()
        summary["users"] = user_count
        print(f"✅ Transferred {user_count} users to Redis!")

    # 2. Sync Chats
    if "chats" in collections:
        chats = list(db.chats.find({}))
        print(f"👥 Found {len(chats)} chats in MongoDB.")
        chat_count = 0
        pipe = r.pipeline()
        for doc in chats:
            cid = str(doc.get("chat_id") or doc.get("_id"))
            if cid:
                pipe.sadd("miko:chats", cid)
                chat_count += 1
        pipe.execute()
        summary["chats"] = chat_count
        print(f"✅ Transferred {chat_count} chats to Redis!")

    # 3. Sync Users Chats
    if "users_chats" in collections:
        users_chats = list(db.users_chats.find({}))
        print(f"📱 Found {len(users_chats)} DM users in MongoDB.")
        uc_count = 0
        pipe = r.pipeline()
        for doc in users_chats:
            uid = str(doc.get("user_id") or doc.get("_id"))
            if uid:
                pipe.sadd("miko:users", uid)
                uc_count += 1
        pipe.execute()
        summary["users_chats"] = uc_count
        print(f"✅ Transferred {uc_count} DM users to Redis!")

    # 4. Sync Sudoers
    if "sudoers" in collections:
        sudoers = list(db.sudoers.find({}))
        print(f"👑 Found {len(sudoers)} sudoers in MongoDB.")
        sudo_count = 0
        pipe = r.pipeline()
        for doc in sudoers:
            uid = str(doc.get("user_id") or doc.get("_id"))
            if uid:
                pipe.sadd("miko:sudoers", uid)
                sudo_count += 1
        pipe.execute()
        summary["sudoers"] = sudo_count
        print(f"✅ Transferred {sudo_count} sudoers to Redis!")

    # 5. Sync any other collections (coupons, group_settings, etc.)
    for coll_name in collections:
        if coll_name in ["users", "chats", "users_chats", "sudoers"]:
            continue
        docs = list(db[coll_name].find({}))
        print(f"📁 Collection '{coll_name}': {len(docs)} documents.")
        pipe = r.pipeline()
        for doc in docs:
            doc_id = str(doc.pop("_id", None))
            if doc_id:
                pipe.set(f"miko:{coll_name}:{doc_id}", json.dumps(doc))
        pipe.execute()
        summary[coll_name] = len(docs)
        print(f"✅ Transferred {len(docs)} items from '{coll_name}' to Redis!")

    print("\n🎉 MIGRATION SUMMARY:")
    for k, v in summary.items():
        print(f"  - {k}: {v} records copied to Redis")

if __name__ == "__main__":
    run_sync()
