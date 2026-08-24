import os
import json
import random
from typing import Optional, Dict, Any, List

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_data.json")
GROUP_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "group_settings.json")

DEFAULT_USER = {
    "username": "User",
    "balance": 0,
    "rank": 0,
    "gems": 0.0,
    "kills": 0,
    "protected": False,
    "last_daily": None,
    "status": "alive",
    "level": 1,
    "xp": 0,
    "xp_max": 1000,
    "emoji": None,
    "premium": False,
    "powers": [],
    "display_name": None,
    "intro_text": None,
    "friends": {},
    "wallet_balance": 0,
    "daily_kills": 0,
    "robs": 0,
    "daily_robs": 0,
    "bomb_wins": 0,
    "prem_wallet": 0.0,
    "past_names": [],
    "past_usernames": [],
    "home_group": None,
}

POWERS_CATALOG: Dict[str, Dict[str, Any]] = {
    "rampage": {
        "name": "Rampage Power",
        "emoji": "🐺",
        "price": 1,
        "desc": "Unleash Miko's fury! Deal massive damage and dominate every battle!",
    },
    "cloak": {
        "name": "Cloak Power",
        "emoji": "🎭",
        "price": 1,
        "desc": "Stay hidden, move silent! Perfect for escape, stealth and surprise attacks!",
    },
    "vault": {
        "name": "Vault Power",
        "emoji": "💎",
        "price": 1,
        "desc": "Secure your rewards! Extra protection for your wealth and rare treasures!",
    },
}


def _migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    changed = False
    for uid, info in data.items():
        for k, v in DEFAULT_USER.items():
            if k not in info:
                info[k] = v if not isinstance(v, (dict, list)) else type(v)()
                changed = True
    if changed:
        save_data(data)
    return data


from modules.utils.db import (
    db_load_user,
    db_save_user,
    db_load_all_users,
    db_load_group,
    db_save_group,
    add_chat,
    rm_chat,
    get_chats,
    add_user_chat,
    rm_user_chat,
    get_user_chats,
)


# In-memory fast cache for instant sub-millisecond lookups
_MEM_CACHE: Dict[str, Any] = {}


def load_data() -> Dict[str, Any]:
    global _MEM_CACHE

    # Load all live users from Redis primary store
    db_users = db_load_all_users()
    if db_users:
        _MEM_CACHE.update(db_users)
        _MEM_CACHE = _migrate(_MEM_CACHE)
        return _MEM_CACHE

    if _MEM_CACHE:
        return _MEM_CACHE

    # Fallback to local file if DB unavailable
    data: Dict[str, Any] = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}

    _MEM_CACHE = _migrate(data)
    return _MEM_CACHE


def save_data(data: Dict[str, Any]) -> None:
    global _MEM_CACHE
    _MEM_CACHE = data
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def get_user(user_id: int, username: str = "User", display_name: Optional[str] = None) -> Dict[str, Any]:
    uid = str(user_id)

    # 1. Check in-memory RAM cache (< 0.001ms)
    if uid in _MEM_CACHE:
        user_doc = _MEM_CACHE[uid]
    else:
        # 2. Check Redis in-memory cache (< 0.5ms)
        user_doc = db_load_user(user_id)
        if not user_doc:
            # 3. Fallback / Create new user
            data = load_data()
            if uid in data:
                user_doc = data[uid]
            else:
                user_doc = dict(DEFAULT_USER)
                user_doc["username"] = username
                user_doc["rank"] = 0
                user_doc["past_usernames"] = [username] if username and username != "User" else []
                if display_name:
                    user_doc["display_name"] = display_name
                    user_doc["past_names"] = [display_name]
                else:
                    user_doc["past_names"] = [username] if username and username != "User" else []
                data[uid] = user_doc
                save_data(data)
                db_save_user(user_id, user_doc)
        _MEM_CACHE[uid] = user_doc

    changed = False
    if display_name and user_doc.get("display_name") != display_name:
        user_doc["display_name"] = display_name
        if display_name not in user_doc.get("past_names", []):
            user_doc.setdefault("past_names", []).append(display_name)
        changed = True
    if username and username != "User" and user_doc.get("username") != username:
        user_doc["username"] = username
        if username not in user_doc.get("past_usernames", []):
            user_doc.setdefault("past_usernames", []).append(username)
        changed = True
    if changed:
        db_save_user(user_id, user_doc)

    for k, v in DEFAULT_USER.items():
        if k not in user_doc:
            user_doc[k] = v if not isinstance(v, (dict, list)) else type(v)()

    return user_doc


def update_user(user_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    uid = str(user_id)
    user_doc = get_user(user_id)
    for k, v in kwargs.items():
        user_doc[k] = v
    _MEM_CACHE[uid] = user_doc
    # Fast instant write to Redis + background sync to Mongo
    db_save_user(user_id, user_doc)
    return user_doc


def add_xp(user_id: int, amount: int) -> Dict[str, Any]:
    user = get_user(user_id)
    xp = (user.get("xp") or 0) + amount
    level = user.get("level") or 1
    xp_max = user.get("xp_max") or 1000
    while xp >= xp_max:
        xp -= xp_max
        level += 1
        xp_max = int(xp_max * 1.35)
    return update_user(user_id, xp=xp, level=level, xp_max=xp_max) or get_user(user_id)


def global_rank(user_id: int, field: str = "balance") -> int:
    data = load_data()
    items = sorted(data.items(), key=lambda x: x[1].get(field, 0), reverse=True)
    for i, (uid, _) in enumerate(items, 1):
        if uid == str(user_id):
            return i
    return len(items) + 1


def get_all_users() -> Dict[str, Any]:
    return load_data()


def load_group_settings() -> Dict[str, Any]:
    if not os.path.exists(GROUP_SETTINGS_FILE):
        return {}
    try:
        with open(GROUP_SETTINGS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_group_settings(data: Dict[str, Any]) -> None:
    with open(GROUP_SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_group(chat_id: int) -> Dict[str, Any]:
    db_data = db_load_group(chat_id)
    if db_data is not None:
        return db_data
    settings = load_group_settings()
    cid = str(chat_id)
    if cid not in settings:
        settings[cid] = {"economy_enabled": True}
        save_group_settings(settings)
    db_save_group(chat_id, settings[cid])
    return settings[cid]


def update_group(chat_id: int, **kwargs) -> Dict[str, Any]:
    settings = load_group_settings()
    cid = str(chat_id)
    if cid not in settings:
        settings[cid] = {"economy_enabled": True}
    db_data = db_load_group(chat_id)
    if db_data:
        settings[cid].update(db_data)
    for k, v in kwargs.items():
        settings[cid][k] = v
    save_group_settings(settings)
    db_save_group(chat_id, settings[cid])
    return settings[cid]


FEATURED_GROUPS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "featured_groups.json")

DEFAULT_FEATURED_GROUPS: List[Dict[str, Any]] = []


def get_featured_groups() -> List[Dict[str, Any]]:
    if not os.path.exists(FEATURED_GROUPS_FILE):
        return []
    try:
        with open(FEATURED_GROUPS_FILE, "r") as f:
            data = json.load(f)
            return list(data.get("groups") or [])
    except Exception:
        return []


def save_featured_groups(groups: List[Dict[str, Any]]) -> None:
    try:
        with open(FEATURED_GROUPS_FILE, "w") as f:
            json.dump({"groups": groups}, f, indent=2)
    except Exception:
        pass


def record_game_stat(user_id: int, game_key: str, won_amount: int = 0, lost_amount: int = 0, is_win: bool = True):
    ud = get_user(user_id)
    stats_key = f"{game_key}_stats"
    stats = ud.get(stats_key) or {}
    if not isinstance(stats, dict):
        stats = {}

    current_wins = stats.get("wins", 0) + (1 if is_win else 0)
    current_losses = stats.get("losses", 0) + (0 if is_win else 1)
    current_won = stats.get("won", 0) + won_amount
    current_lost = stats.get("lost", 0) + lost_amount

    streak = stats.get("streak", 0)
    if is_win:
        streak += 1
    else:
        streak = 0
    max_streak = max(stats.get("max_streak", 0), streak)

    stats["wins"] = current_wins
    stats["losses"] = current_losses
    stats["won"] = current_won
    stats["lost"] = current_lost
    stats["streak"] = streak
    stats["max_streak"] = max_streak

    update_user(user_id, **{stats_key: stats})
