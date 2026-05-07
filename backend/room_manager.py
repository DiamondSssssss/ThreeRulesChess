"""
room_manager.py — Quản lý phòng in-memory
Không dùng DB cho game state (chỉ dùng MongoDB lưu kết quả sau ván).
"""
import uuid
import time
from typing import Optional
from chess_engine import GameEngine


class Player:
    def __init__(self, user_id: str, username: str, sid: str, color: str):
        self.user_id  = user_id
        self.username = username
        self.sid      = sid      # socket.io session id
        self.color    = color    # "white" | "black"
        self.online   = True
        self.clock    = 600.0    # giây còn lại (mặc định 10 phút)
        self.last_tick: Optional[float] = None  # timestamp bắt đầu lượt

    def to_dict(self) -> dict:
        return {
            "user_id":  self.user_id,
            "username": self.username,
            "color":    self.color,
            "online":   self.online,
            "clock":    round(self.clock, 1),
        }


class Room:
    def __init__(self, room_id: str, time_control: int = 600):
        self.room_id      = room_id
        self.time_control = time_control  # giây
        self.players: dict[str, Player] = {}  # color -> Player
        self.engine       = GameEngine()
        self.created_at   = time.time()
        self.started      = False
        self.spectators: list[str] = []  # list sid
        self.host_id: Optional[str] = None

    # ─── Player management ────────────────────────────────────────────────

    def add_player(self, user_id: str, username: str, sid: str) -> Optional[Player]:
        """
        Thêm người chơi vào phòng.
        Trả Player hoặc None nếu phòng đầy.
        """
        if not self.host_id:
            self.host_id = user_id
            
        taken_colors = set(self.players.keys())
        if "white" not in taken_colors:
            color = "white"
        elif "black" not in taken_colors:
            color = "black"
        else:
            return None  # Phòng đầy

        p = Player(user_id, username, sid, color)
        p.clock = float(self.time_control)
        self.players[color] = p
        return p

    def reset_for_rematch(self):
        self.engine = GameEngine()
        self.started = False
        for p in self.players.values():
            p.clock = float(self.time_control)
            p.last_tick = None

    def assign_colors(self, host_choice: str):
        if len(self.players) < 2: return
        import random
        if host_choice == "random":
            host_choice = random.choice(["white", "black"])
            
        p1, p2 = list(self.players.values())
        if p1.user_id == self.host_id:
            host_p, guest_p = p1, p2
        else:
            host_p, guest_p = p2, p1
            
        host_p.color = host_choice
        guest_p.color = "black" if host_choice == "white" else "white"
        
        self.players = {
            host_p.color: host_p,
            guest_p.color: guest_p
        }

    def remove_player(self, sid: str):
        for color, p in list(self.players.items()):
            if p.sid == sid:
                p.online = False
                break

    def rejoin_player(self, user_id: str, new_sid: str) -> Optional[Player]:
        for p in self.players.values():
            if p.user_id == user_id:
                p.sid    = new_sid
                p.online = True
                return p
        return None

    def get_player_by_sid(self, sid: str) -> Optional[Player]:
        for p in self.players.values():
            if p.sid == sid:
                return p
        return None

    def get_player_by_color(self, color: str) -> Optional[Player]:
        return self.players.get(color)

    def is_full(self) -> bool:
        return len(self.players) == 2

    def opponent_of(self, color: str) -> Optional[Player]:
        opp_color = "black" if color == "white" else "white"
        return self.players.get(opp_color)

    # ─── Clock management ────────────────────────────────────────────────

    def start_clock(self, color: str):
        p = self.players.get(color)
        if p:
            p.last_tick = time.time()

    def stop_clock(self, color: str):
        p = self.players.get(color)
        if p and p.last_tick is not None:
            elapsed  = time.time() - p.last_tick
            p.clock  = max(0.0, p.clock - elapsed)
            p.last_tick = None

    def tick_clocks(self) -> Optional[str]:
        """
        Cập nhật đồng hồ đang chạy.
        Trả màu hết giờ hoặc None.
        """
        current = self.engine.current_player_str()
        p = self.players.get(current)
        if p and p.last_tick is not None:
            now     = time.time()
            elapsed = now - p.last_tick
            p.clock = max(0.0, p.clock - elapsed)
            p.last_tick = now
            if p.clock <= 0:
                return current
        return None

    def deduct_time(self, color: str, seconds: float):
        """Trừ giây từ đồng hồ (dùng cho Time Warp rule)."""
        p = self.players.get(color)
        if p:
            p.clock = max(0.0, p.clock - seconds)

    # ─── Info ────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "room_id":      self.room_id,
            "started":      self.started,
            "time_control": self.time_control,
            "host_id":      self.host_id,
            "players":      {c: p.to_dict() for c, p in self.players.items()},
            "spectators":   len(self.spectators),
        }


# ──────────────────────────────────────────────────────────────────────────────
# RoomManager singleton
# ──────────────────────────────────────────────────────────────────────────────

class RoomManager:
    def __init__(self):
        self._rooms: dict[str, Room] = {}

    def create_room(self, time_control: int = 600) -> Room:
        room_id = str(uuid.uuid4())[:8].upper()
        self._rooms[room_id] = Room(room_id, time_control)
        return self._rooms[room_id]

    def get_room(self, room_id: str) -> Optional[Room]:
        return self._rooms.get(room_id.upper())

    def delete_room(self, room_id: str):
        self._rooms.pop(room_id.upper(), None)

    def find_room_by_sid(self, sid: str) -> Optional[Room]:
        for room in self._rooms.values():
            if room.get_player_by_sid(sid):
                return room
            if sid in room.spectators:
                return room
        return None

    def all_rooms(self) -> list[dict]:
        return [r.to_dict() for r in self._rooms.values()]

    def cleanup_empty_rooms(self):
        """Xóa phòng không có ai online sau 10 phút."""
        now  = time.time()
        dead = [
            rid for rid, room in self._rooms.items()
            if not any(p.online for p in room.players.values())
            and (now - room.created_at) > 600
        ]
        for rid in dead:
            del self._rooms[rid]


# Module-level singleton
room_manager = RoomManager()
