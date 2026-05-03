import os
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv
from datetime import datetime, timezone
from bson import ObjectId

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ Đã kết nối thành công tới MongoDB Atlas!")
except Exception as e:
    print("❌ Lỗi kết nối MongoDB:", e)
    client = None

DB_NAME = os.getenv("DB_NAME", "threeruleschess")
db = client.get_database(DB_NAME) if client else None
users_collection = db["Users"] if db is not None else None
matches_collection = db["Matches"] if db is not None else None

# Tạo unique index cho username
if users_collection is not None:
    users_collection.create_index([("username", ASCENDING)], unique=True)


# ─── USERS ───────────────────────────────────────────────

def create_user(username: str, password_hash: str):
    """Tạo người chơi mới, trả về inserted_id hoặc None nếu username đã tồn tại."""
    new_user = {
        "username": username,
        "password_hash": password_hash,
        "elo": 1000,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = users_collection.insert_one(new_user)
        return result.inserted_id
    except Exception:
        return None  # Trùng username


def find_user_by_username(username: str):
    """Tìm user theo username, trả về dict hoặc None."""
    return users_collection.find_one({"username": username})


def find_user_by_id(user_id: str):
    """Tìm user theo _id string."""
    try:
        return users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


def update_elo(user_id: str, new_elo: int):
    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"elo": new_elo}}
    )


# ─── MATCHES ─────────────────────────────────────────────

def save_match(player1_id, player2_id, winner, moves_history, rules_applied):
    """Lưu lịch sử trận đấu sau khi kết thúc."""
    match_data = {
        "player1_id": player1_id,
        "player2_id": player2_id,
        "winner": winner,
        "moves_history": moves_history,     # ["e2e4", "e7e5", ...]
        "rules_applied": rules_applied,     # [{"id": "r01", "name": "...", "ply": 3}, ...]
        "played_at": datetime.now(timezone.utc),
    }
    result = matches_collection.insert_one(match_data)
    return result.inserted_id


def save_match_result(white_id: str, black_id: str, result: str,
                      move_history: list, active_rules: list,
                      reason: str = "normal", played_at: str = None):
    """
    API được app.py gọi sau mỗi game over.
    result: 'white' | 'black' | 'draw'
    """
    if matches_collection is None:
        return None
    doc = {
        "white_id":     white_id,
        "black_id":     black_id,
        "result":       result,
        "reason":       reason,
        "move_history": move_history,
        "active_rules": active_rules,
        "played_at":    played_at or datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = matches_collection.insert_one(doc)
        return str(res.inserted_id)
    except Exception as e:
        print(f"[DB] save_match_result error: {e}")
        return None