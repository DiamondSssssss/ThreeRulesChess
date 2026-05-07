"""
chess_engine.py — GameEngine: bọc chess.Board + quản lý extra rules lifecycle
Trigger mỗi 3 ply → người đi nước thứ 3 chọn 1 trong 3 luật đề xuất
Max 3 luật active → đủ thì không trigger
Mỗi luật sống 9 ply (tự hết)
"""
import chess
from typing import Optional
from extra_rules import get_random_rule_choices, apply_rule, rule_info

TRIGGER_INTERVAL = 5    # ply
MAX_ACTIVE_RULES  = 3   # tối đa
RULE_LIFETIME     = 10   # ply


class ActiveRule:
    """Đại diện một luật đang active."""
    def __init__(self, rule_id: str, chosen_at_ply: int):
        self.rule_id       = rule_id
        self.chosen_at_ply = chosen_at_ply
        self.expires_at    = chosen_at_ply + RULE_LIFETIME

    def is_alive(self, current_ply: int) -> bool:
        return current_ply < self.expires_at

    def to_dict(self) -> dict:
        r_info = rule_info(self.rule_id) or {}
        return {
            "rule_id":        self.rule_id,
            "chosen_at_ply":  self.chosen_at_ply,
            "expires_at":     self.expires_at,
            **r_info,  # name + description + type
        }


class GameEngine:
    """
    Wrapper quản lý trạng thái game + extra rules.
    Thread-safe nếu dùng eventlet (GIL).
    """

    def __init__(self, fen: str = chess.STARTING_FEN):
        self.board          = chess.Board(fen)
        self.ply_count      = 0          # số half-move đã thực hiện
        self.active_rules:  list[ActiveRule] = []
        self.pending_rule_choices: Optional[list[dict]] = None  # 3 luật chờ chọn
        self.pending_for_player: Optional[chess.Color]  = None  # người cần chọn

        # Lịch sử quân bị ăn theo màu, dùng cho Necromancer
        self.captured: dict[chess.Color, list[chess.Piece]] = {
            chess.WHITE: [], chess.BLACK: []
        }

        # Lịch sử move (uci string) để client replay
        self.move_history: list[str] = []

        # Trạng thái game-over
        self.game_over     = False
        self.game_result   = None  # "white" | "black" | "draw"

        # Luật đặc biệt cần theo dõi ở tầng engine
        self._skipped_turn: Optional[chess.Color] = None  # Timestop
        self._frozen_column: Optional[int]         = None  # Blizzard
        self._frozen_col_exp: int                  = 0
        self._gravity_reversed: set[chess.Color]   = set()  # Reverse Gravity

    # ─────────────────────────── Helpers ────────────────────────────────────

    def current_player(self) -> chess.Color:
        return self.board.turn

    def current_player_str(self) -> str:
        return "white" if self.board.turn == chess.WHITE else "black"

    def _prune_expired_rules(self):
        before = len(self.active_rules)
        self.active_rules = [r for r in self.active_rules if r.is_alive(self.ply_count)]
        if len(self.active_rules) < before:
            pass  # Caller may emit event

    def active_rule_ids(self) -> list[str]:
        return [r.rule_id for r in self.active_rules]

    def active_rules_info(self) -> list[dict]:
        return [r.to_dict() for r in self.active_rules]

    def _should_trigger_rule(self) -> bool:
        """Trả True nếu ply này là bội số của TRIGGER_INTERVAL và còn slot."""
        return (
            self.ply_count > 0
            and self.ply_count % TRIGGER_INTERVAL == 0
            and len(self.active_rules) < MAX_ACTIVE_RULES
        )

    # ─────────────────────────── Rule management ────────────────────────────

    def prepare_rule_choices(self) -> list[dict]:
        """Chuẩn bị 3 luật ngẫu nhiên để người chơi chọn."""
        choices = get_random_rule_choices(self.active_rule_ids(), count=3)
        self.pending_rule_choices = choices
        self.pending_for_player   = not self.board.turn  # người VỪA đi (sau push board.turn đã đổi)
        return choices

    def confirm_rule_choice(self, rule_id: str, player_color: chess.Color) -> dict:
        """
        Xác nhận luật người chơi chọn.
        Trả {"ok": True, "rule": {...}} hoặc {"ok": False, "error": "..."}
        """
        if self.pending_rule_choices is None:
            return {"ok": False, "error": "Không có luật chờ chọn"}

        valid_ids = [r["id"] for r in self.pending_rule_choices]
        if rule_id not in valid_ids:
            return {"ok": False, "error": "Luật không hợp lệ"}

        new_rule = ActiveRule(rule_id, self.ply_count)
        self.active_rules.append(new_rule)
        self.pending_rule_choices = None
        self.pending_for_player   = None

        r_info = rule_info(rule_id)
        if r_info and r_info.get("type") == "instant":
            apply_rule(rule_id, self.board, chess.Move.null()) # instant rules don't need move

        # Xử lý các luật đặc biệt cần track ngay
        self._on_rule_activated(rule_id)

        return {"ok": True, "rule": new_rule.to_dict()}

    def _on_rule_activated(self, rule_id: str):
        """Khởi tạo trạng thái cục bộ cho các luật cần theo dõi."""
        if rule_id == "blizzard":
            import random
            self._frozen_column  = random.randint(0, 7)
            self._frozen_col_exp = self.ply_count + RULE_LIFETIME
        elif rule_id == "reverse_gravity":
            self._gravity_reversed.add(self.board.turn)
        elif rule_id == "timestop":
            self._skipped_turn = chess.BLACK if self.board.turn == chess.WHITE else chess.WHITE

    # ─────────────────────────── Move validation & push ─────────────────────

    def is_legal_move(self, uci: str) -> tuple[bool, Optional[chess.Move]]:
        """Kiểm tra hợp lệ (kể cả active rules). Trả (bool, move|None)."""
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False, None

        if move not in self.board.legal_moves:
            return False, None

        # Blizzard: cột bị phong tỏa
        if (self._frozen_column is not None
                and self.ply_count < self._frozen_col_exp):
            if (chess.square_file(move.from_square) == self._frozen_column
                    or chess.square_file(move.to_square) == self._frozen_column):
                return False, None

        # Queen Aura: không thể ăn quân được bảo vệ trong phạm vi 2 ô quanh Hậu đối thủ
        if "queen_aura" in self.active_rule_ids():
            mover_color = self.board.turn
            opp_color   = chess.BLACK if mover_color == chess.WHITE else chess.WHITE
            opp_queens  = list(self.board.pieces(chess.QUEEN, opp_color))
            if opp_queens and self.board.is_capture(move):
                target = move.to_square
                for qsq in opp_queens:
                    if chess.square_distance(qsq, target) <= 2:
                        return False, None

        return True, move

    def push_move(self, uci: str) -> dict:
        """
        Thực hiện nước đi, áp dụng side-effects của các luật active.
        Trả payload event.
        """
        ok, move = self.is_legal_move(uci)
        if not ok:
            return {"ok": False, "error": "Nước đi không hợp lệ"}

        # Ghi lại quân bị ăn trước khi push (cho Necromancer)
        captured_piece = None
        if self.board.is_capture(move):
            captured_piece = self.board.piece_at(move.to_square)

        mover_color = self.board.turn
        self.board.push(move)
        self.ply_count += 1
        self.move_history.append(uci)

        if captured_piece:
            opp = chess.BLACK if mover_color == chess.WHITE else chess.WHITE
            self.captured[opp].append(captured_piece)

        # Necromancer: hồi sinh quân vừa bị ăn của người bị ăn
        if "necromancer" in self.active_rule_ids() and captured_piece:
            import random
            empties = [sq for sq in chess.SQUARES if self.board.piece_at(sq) is None]
            if empties:
                revival_sq = random.choice(empties)
                self.board.set_piece_at(revival_sq, captured_piece)

        # Timestop: bỏ qua lượt
        if (self._skipped_turn is not None
                and self.board.turn == self._skipped_turn
                and "timestop" in self.active_rule_ids()):
            self.board.push(chess.Move.null())
            self.ply_count += 1
            self._skipped_turn = None

        # Áp dụng side-effects của từng luật active (theo thứ tự)
        side_effect_log = []
        for ar in list(self.active_rules):
            if ar.is_alive(self.ply_count):
                r_info = rule_info(ar.rule_id)
                if r_info and r_info.get("type") == "on_move":
                    if ar.rule_id == "knight_charge":
                        if captured_piece and self.board.piece_at(move.to_square) and self.board.piece_at(move.to_square).piece_type == chess.KNIGHT:
                            knight_sq = move.to_square
                            self.board.turn = mover_color
                            legal_jumps = []
                            for m in self.board.legal_moves:
                                if m.from_square == knight_sq:
                                    target_piece = self.board.piece_at(m.to_square)
                                    if target_piece and target_piece.piece_type == chess.KING:
                                        continue
                                    legal_jumps.append(m)
                            self.board.turn = not mover_color
                            
                            if legal_jumps:
                                import random
                                extra_move = random.choice(legal_jumps)
                                self.board.turn = mover_color
                                self.board.push(extra_move)
                                self.ply_count += 1
                                self.move_history.append(extra_move.uci())
                                side_effect_log.append("knight_charge")
                                
                    elif ar.rule_id == "explosive_pawn":
                        if captured_piece and captured_piece.piece_type == chess.PAWN:
                            for s in chess.SquareSet(chess.BB_KING_ATTACKS[move.to_square]):
                                p = self.board.piece_at(s)
                                if p and p.piece_type != chess.KING:
                                    self.board.remove_piece_at(s)
                            side_effect_log.append("explosive_pawn")
                            
                    elif ar.rule_id == "ghost_pawn":
                        if self.board.piece_at(move.to_square) and self.board.piece_at(move.to_square).piece_type == chess.PAWN:
                            import random
                            empties = [sq for sq in chess.SQUARES if self.board.piece_at(sq) is None]
                            if empties:
                                sq = random.choice(empties)
                                self.board.set_piece_at(sq, chess.Piece(chess.PAWN, mover_color))
                            side_effect_log.append("ghost_pawn")
                else:
                    applied = apply_rule(ar.rule_id, self.board, move)
                    if applied:
                        side_effect_log.append(ar.rule_id)

        # Dọn luật hết hạn
        self._prune_expired_rules()

        # Kiểm tra kết thúc game
        trigger_choices = None
        if self.board.is_game_over():
            self.game_over = True
            result = self.board.result()
            if result == "1-0":
                self.game_result = "white"
            elif result == "0-1":
                self.game_result = "black"
            else:
                self.game_result = "draw"
        elif self._should_trigger_rule():
            trigger_choices = self.prepare_rule_choices()

        return {
            "ok":            True,
            "fen":           self.board.fen(),
            "ply":           self.ply_count,
            "mover":         "white" if mover_color == chess.WHITE else "black",
            "next_turn":     self.current_player_str(),
            "active_rules":  self.active_rules_info(),
            "side_effects":  side_effect_log,
            "game_over":     self.game_over,
            "game_result":   self.game_result,
            "trigger_choices": trigger_choices,  # None hoặc list 3 luật
            "last_move":     uci,
            "move_history":  self.move_history,
        }

    # ─────────────────────────── State snapshot ─────────────────────────────

    def snapshot(self) -> dict:
        """Full state để sync khi client kết nối lại."""
        return {
            "fen":             self.board.fen(),
            "ply":             self.ply_count,
            "move_history":    self.move_history,
            "active_rules":    self.active_rules_info(),
            "game_over":       self.game_over,
            "game_result":     self.game_result,
            "pending_choices": self.pending_rule_choices,
            "pending_for":     (
                "white" if self.pending_for_player == chess.WHITE
                else "black" if self.pending_for_player == chess.BLACK
                else None
            ),
            "current_turn":    self.current_player_str(),
        }
