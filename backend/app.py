"""
app.py — Flask + Socket.IO server chính
Ghép: auth, room_manager, chess_engine, extra_rules
"""
import os
import chess
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_cors import CORS

from auth import auth_bp, token_required
from database import save_match_result
from room_manager import room_manager
from extra_rules import all_rule_infos

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "threerules_secret")

CORS(app, resources={r"/api/*": {"origins": "*"}})

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)

# Register auth blueprint
app.register_blueprint(auth_bp)

# ──────────────────────────────────────────────────────────────────────────────
# REST endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return jsonify({"message": "ThreeRulesChess API Server is running!"})


@app.route("/api/rules", methods=["GET"])
def list_rules():
    """Trả danh sách tất cả 30 luật."""
    return jsonify(all_rule_infos())


@app.route("/api/rooms", methods=["GET"])
def list_rooms():
    return jsonify(room_manager.all_rooms())


@app.route("/api/rooms", methods=["POST"])
@token_required
def create_room():
    data = request.get_json(silent=True) or {}
    time_control = int(data.get("time_control", 600))
    time_control = max(30, min(3600, time_control))  # clamp 30s – 60m
    room = room_manager.create_room(time_control)
    return jsonify({"room_id": room.room_id, "time_control": time_control}), 201


@app.route("/api/rooms/<room_id>", methods=["GET"])
def room_state(room_id):
    room = room_manager.get_room(room_id)
    if not room:
        return jsonify({"error": "Không tìm thấy phòng"}), 404
    return jsonify({**room.to_dict(), **room.engine.snapshot()})


# ──────────────────────────────────────────────────────────────────────────────
# Socket.IO events
# ──────────────────────────────────────────────────────────────────────────────

def _emit_board_update(room_id: str, result: dict):
    """Broadcast board state to room."""
    socketio.emit("board_update", result, to=room_id)


def _emit_clocks(room_id: str, room):
    clocks = {c: round(p.clock, 1) for c, p in room.players.items()}
    socketio.emit("clock_update", clocks, to=room_id)


# ── join_room ──────────────────────────────────────────────────────────────

@socketio.on("join")
def on_join(data):
    """
    Payload: {room_id, token}
    """
    import jwt as pyjwt
    JWT_SECRET = os.getenv("JWT_SECRET", "threeruleschess_secret_key_change_me")

    token   = data.get("token", "")
    room_id = (data.get("room_id") or "").strip().upper()

    # Decode token
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        emit("error", {"message": "Token không hợp lệ"})
        return

    user_id  = payload["sub"]
    username = payload["username"]
    sid      = request.sid

    room = room_manager.get_room(room_id)
    if not room:
        emit("error", {"message": "Phòng không tồn tại"})
        return

    # Kiểm tra reconnect
    player = room.rejoin_player(user_id, sid)
    if player is None:
        player = room.add_player(user_id, username, sid)
        if player is None:
            # Phòng đầy → spectator
            room.spectators.append(sid)
            join_room(room_id)
            emit("joined_as_spectator", {
                "snapshot": room.engine.snapshot(),
                "room_info": room.to_dict(),
            })
            return

    join_room(room_id)
    emit("joined", {
        "color":    player.color,
        "room_id":  room_id,
        "snapshot": room.engine.snapshot(),
        "room_info": room.to_dict(),
    })

    # Thông báo đối thủ
    socketio.emit("opponent_joined", {
        "username": username,
        "color":    player.color,
        "online":   True,
    }, to=room_id, skip_sid=sid)

    # Nếu đủ 2 người và chưa bắt đầu
    if room.is_full() and not room.started:
        socketio.emit("room_ready", {}, to=room_id)


# ── move ──────────────────────────────────────────────────────────────────────

@socketio.on("move")
def on_move(data):
    """
    Payload: {room_id, uci, token}
    uci: e.g. "e2e4", "e7e8q"
    """
    import jwt as pyjwt
    JWT_SECRET = os.getenv("JWT_SECRET", "threeruleschess_secret_key_change_me")

    room_id = (data.get("room_id") or "").strip().upper()
    uci     = (data.get("uci") or "").strip()
    token   = data.get("token", "")

    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        emit("error", {"message": "Token không hợp lệ"})
        return

    user_id = payload["sub"]
    room = room_manager.get_room(room_id)
    if not room or not room.started:
        emit("error", {"message": "Phòng không tồn tại hoặc chưa bắt đầu"})
        return

    player = room.get_player_by_sid(request.sid)
    if not player:
        emit("error", {"message": "Bạn không trong phòng này"})
        return

    # Kiểm tra lượt
    current_turn = room.engine.current_player_str()
    if player.color != current_turn:
        emit("error", {"message": "Chưa đến lượt của bạn"})
        return

    # Kiểm tra pending rule (phải chọn trước khi đi)
    if room.engine.pending_rule_choices is not None:
        emit("error", {"message": "Bạn cần chọn luật trước khi đi nước tiếp"})
        return

    # Dừng đồng hồ người vừa đi
    room.stop_clock(player.color)

    # Thực thi move
    result = room.engine.push_move(uci)
    if not result["ok"]:
        room.start_clock(player.color)  # rollback clock
        emit("error", {"message": result["error"]})
        return

    # Áp dụng Time Warp nếu đang active
    if "time_warp" in room.engine.active_rule_ids():
        opp = room.opponent_of(player.color)
        if opp:
            room.deduct_time(opp.color, 30.0)

    # Bắt đồng hồ người tiếp theo (nếu game chưa over)
    if not result["game_over"]:
        room.start_clock(result["next_turn"])

    # Broadcast
    _emit_board_update(room_id, result)
    _emit_clocks(room_id, room)

    # Nếu cần chọn luật → yêu cầu người vừa đi (mover) chọn
    if result.get("trigger_choices"):
        socketio.emit("rule_trigger", {
            "choices":    result["trigger_choices"],
            "for_player": result["mover"],
        }, to=room_id)

    # Game over
    if result["game_over"]:
        _handle_game_over(room, room_id, result["game_result"])


# ── choose_rule ────────────────────────────────────────────────────────────────

@socketio.on("choose_rule")
def on_choose_rule(data):
    """
    Payload: {room_id, rule_id, token}
    """
    import jwt as pyjwt
    JWT_SECRET = os.getenv("JWT_SECRET", "threeruleschess_secret_key_change_me")

    room_id = (data.get("room_id") or "").strip().upper()
    rule_id = data.get("rule_id", "")
    token   = data.get("token", "")

    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        emit("error", {"message": "Token không hợp lệ"})
        return

    room = room_manager.get_room(room_id)
    if not room:
        emit("error", {"message": "Phòng không tồn tại"})
        return

    player = room.get_player_by_sid(request.sid)
    if not player:
        emit("error", {"message": "Bạn không trong phòng này"})
        return

    # Kiểm tra đúng người cần chọn
    pending_for = room.engine.pending_for_player
    if pending_for is not None:
        expected_color = "white" if pending_for == chess.WHITE else "black"
        if player.color != expected_color:
            emit("error", {"message": "Không phải lượt chọn luật của bạn"})
            return

    chess_color = chess.WHITE if player.color == "white" else chess.BLACK
    res = room.engine.confirm_rule_choice(rule_id, chess_color)

    if not res["ok"]:
        emit("error", {"message": res["error"]})
        return

    socketio.emit("rule_activated", {
        "rule":         res["rule"],
        "active_rules": room.engine.active_rules_info(),
        "chosen_by":    player.color,
    }, to=room_id)
    
    # Send a board update so frontend sees any instant modifications or turn changes (e.g. from Timestop)
    snapshot = room.engine.snapshot()
    _emit_board_update(room_id, {
        "ok": True,
        "fen": snapshot["fen"],
        "ply": snapshot["ply"],
        "next_turn": snapshot["current_turn"],
        "active_rules": snapshot["active_rules"],
        "move_history": snapshot["move_history"],
        "game_over": snapshot["game_over"],
        "game_result": snapshot["game_result"]
    })


# ── resign ─────────────────────────────────────────────────────────────────────

@socketio.on("resign")
def on_resign(data):
    import jwt as pyjwt
    JWT_SECRET = os.getenv("JWT_SECRET", "threeruleschess_secret_key_change_me")

    room_id = (data.get("room_id") or "").strip().upper()
    token   = data.get("token", "")

    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        emit("error", {"message": "Token không hợp lệ"})
        return

    room = room_manager.get_room(room_id)
    if not room:
        return

    player = room.get_player_by_sid(request.sid)
    if not player:
        return

    winner = "black" if player.color == "white" else "white"
    room.engine.game_over   = True
    room.engine.game_result = winner
    _handle_game_over(room, room_id, winner, reason="resign")


# ── offer_draw / accept_draw ───────────────────────────────────────────────────

@socketio.on("offer_draw")
def on_offer_draw(data):
    room_id = (data.get("room_id") or "").strip().upper()
    room = room_manager.get_room(room_id)
    if not room:
        return
    player = room.get_player_by_sid(request.sid)
    if not player:
        return
    opp = room.opponent_of(player.color)
    if opp:
        socketio.emit("draw_offered", {"by": player.color}, to=opp.sid)


@socketio.on("accept_draw")
def on_accept_draw(data):
    room_id = (data.get("room_id") or "").strip().upper()
    room = room_manager.get_room(room_id)
    if not room:
        return
    room.engine.game_over   = True
    room.engine.game_result = "draw"
    _handle_game_over(room, room_id, "draw", reason="agreement")

# ── start_match ───────────────────────────────────────────────────────────────

@socketio.on("start_match")
def on_start_match(data):
    import jwt as pyjwt
    JWT_SECRET = os.getenv("JWT_SECRET", "threeruleschess_secret_key_change_me")
    room_id = (data.get("room_id") or "").strip().upper()
    color_choice = data.get("color_choice", "random")
    token = data.get("token", "")

    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return

    room = room_manager.get_room(room_id)
    if not room or not room.is_full():
        return
        
    player = room.get_player_by_sid(request.sid)
    if not player or player.user_id != room.host_id:
        return
        
    room.assign_colors(color_choice)
    room.started = True
    room.engine.game_over = False
    
    first_color = room.engine.current_player_str()
    
    socketio.emit("match_started", {
        "message":    "Ván cờ bắt đầu!",
        "first_turn": first_color,
        "time_control": room.time_control,
        "room_info":  room.to_dict(),
        "snapshot":   room.engine.snapshot(),
    }, to=room_id)
    _emit_clocks(room_id, room)

# ── rematch ───────────────────────────────────────────────────────────────────

@socketio.on("rematch")
def on_rematch(data):
    import jwt as pyjwt
    JWT_SECRET = os.getenv("JWT_SECRET", "threeruleschess_secret_key_change_me")
    room_id = (data.get("room_id") or "").strip().upper()
    token = data.get("token", "")

    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return

    room = room_manager.get_room(room_id)
    if not room:
        return
        
    player = room.get_player_by_sid(request.sid)
    if not player or player.user_id != room.host_id:
        return
        
    room.reset_for_rematch()
    socketio.emit("room_reset", {
        "room_info": room.to_dict(),
        "snapshot": room.engine.snapshot()
    }, to=room_id)
    if room.is_full():
        socketio.emit("room_ready", {}, to=room_id)


# ── disconnect ─────────────────────────────────────────────────────────────────

@socketio.on("disconnect")
def on_disconnect():
    room = room_manager.find_room_by_sid(request.sid)
    if not room:
        return
    player = room.get_player_by_sid(request.sid)
    if player:
        room.remove_player(request.sid)
        socketio.emit("opponent_left", {
            "username": player.username,
            "color":    player.color,
        }, to=room.room_id)
    elif request.sid in room.spectators:
        room.spectators.remove(request.sid)

    _cleanup_room_if_empty(room.room_id)


# ── leave_room (chủ động rời phòng, khác với disconnect) ───────────────────────

@socketio.on("leave_room")
def on_leave_room(data):
    """
    Client chủ động rời phòng (nhấn nút '← Sảnh').
    Payload: {room_id, token}
    """
    room_id = (data.get("room_id") or "").strip().upper()
    room    = room_manager.get_room(room_id)
    if not room:
        return

    player = room.get_player_by_sid(request.sid)
    if player:
        # Âm báo đối thủ
        socketio.emit("opponent_left", {
            "username": player.username,
            "color":    player.color,
        }, to=room_id, skip_sid=request.sid)
        room.remove_player(request.sid)
    elif request.sid in room.spectators:
        room.spectators.remove(request.sid)

    leave_room(room_id)  # Rời socket room
    _cleanup_room_if_empty(room_id)


def _cleanup_room_if_empty(room_id: str):
    """
    Xóa phòng ngay nếu không còn ai online.
    Nếu vẫn còn người (offline tạm thời) thì giữ lại 10 phút để có thể reconnect.
    """
    room = room_manager.get_room(room_id)
    if not room:
        return
    online_players = [p for p in room.players.values() if p.online]
    if not online_players and not room.spectators:
        room_manager.delete_room(room_id)
        print(f"[Room] {room_id} deleted (empty)")
    else:
        room_manager.cleanup_empty_rooms()  # Dọn các phòng cũ hơn 10 phút


# ──────────────────────────────────────────────────────────────────────────────
# Background clock ticker (eventlet green thread)
# ──────────────────────────────────────────────────────────────────────────────

def _clock_ticker():
    import time
    while True:
        time.sleep(1)
        for room_id, room in list(room_manager._rooms.items()):
            if not room.started or room.engine.game_over:
                continue
            loser = room.tick_clocks()
            if loser:
                winner = "black" if loser == "white" else "white"
                room.engine.game_over   = True
                room.engine.game_result = winner
                _handle_game_over(room, room_id, winner, reason="timeout")
            else:
                _emit_clocks(room_id, room)


# ──────────────────────────────────────────────────────────────────────────────
# Game over handler
# ──────────────────────────────────────────────────────────────────────────────

def _handle_game_over(room, room_id: str, result: str, reason: str = "normal"):
    socketio.emit("game_over", {
        "result": result,   # "white" | "black" | "draw"
        "reason": reason,   # "normal" | "resign" | "timeout" | "agreement"
        "fen":    room.engine.board.fen(),
    }, to=room_id)

    # Lưu kết quả vào MongoDB
    white = room.players.get("white")
    black = room.players.get("black")
    if white and black:
        try:
            save_match_result(
                white_id=white.user_id,
                black_id=black.user_id,
                result=result,
                move_history=room.engine.move_history,
                active_rules=[r["rule_id"] for r in room.engine.active_rules_info()],
                reason=reason,
                played_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            print(f"[WARN] save_match_result failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=_clock_ticker, daemon=True)
    t.start()

    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    print(f"[ThreeRulesChess] Listening on http://0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=debug, allow_unsafe_werkzeug=True)
