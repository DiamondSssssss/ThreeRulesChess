"""
auth.py — Đăng ký / Đăng nhập / JWT middleware
"""
import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Blueprint, request, jsonify
from database import create_user, find_user_by_username

auth_bp = Blueprint("auth", __name__)

JWT_SECRET = os.getenv("JWT_SECRET", "threeruleschess_secret_key_change_me")
JWT_ALGO = "HS256"
JWT_EXPIRY_HOURS = 24


def _make_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def token_required(f):
    """Decorator bảo vệ route, inject g.current_user vào request context."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            return jsonify({"error": "Token thiếu"}), 401
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token hết hạn"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token không hợp lệ"}), 401
        request.current_user = {"id": data["sub"], "username": data["username"]}
        return f(*args, **kwargs)
    return decorated


# ─── ROUTES ──────────────────────────────────────────────

@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Thiếu username hoặc password"}), 400
    if len(username) < 3 or len(username) > 20:
        return jsonify({"error": "Username phải từ 3-20 ký tự"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password phải ít nhất 6 ký tự"}), 400

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = create_user(username, pw_hash)

    if user_id is None:
        return jsonify({"error": "Username đã tồn tại"}), 409

    token = _make_token(str(user_id), username)
    return jsonify({"token": token, "username": username}), 201


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = find_user_by_username(username)
    if not user:
        return jsonify({"error": "Sai username hoặc password"}), 401

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify({"error": "Sai username hoặc password"}), 401

    token = _make_token(str(user["_id"]), user["username"])
    return jsonify({
        "token": token,
        "username": user["username"],
        "elo": user.get("elo", 1000),
    }), 200
