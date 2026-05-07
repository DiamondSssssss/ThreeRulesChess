"""
extra_rules.py — Kho 30 luật tùy chỉnh + hàm random
Mỗi rule là một dict:
  id          : str   — mã định danh duy nhất
  name        : str   — tên hiển thị
  description : str   — mô tả ngắn cho người chơi
  apply       : callable(board, move) -> None   (biến đổi board sau move)
  check       : callable(board) -> bool          (kiểm tra điều kiện kích hoạt tức thì, tuỳ chọn)
Luật sống 9 ply kể từ khi được chọn; tự hết khi đủ ply.
"""
import random
import chess

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS nội bộ
# ──────────────────────────────────────────────────────────────────────────────

def _random_empty_square(board: chess.Board) -> chess.Square | None:
    empties = [sq for sq in chess.SQUARES if board.piece_at(sq) is None]
    return random.choice(empties) if empties else None


def _squares_of_piece(board: chess.Board, piece_type, color) -> list[chess.Square]:
    return list(board.pieces(piece_type, color))


def _opponent(color: chess.Color) -> chess.Color:
    return chess.BLACK if color == chess.WHITE else chess.WHITE


# ──────────────────────────────────────────────────────────────────────────────
# ĐỊNH NGHĨA 30 LUẬT
# ──────────────────────────────────────────────────────────────────────────────

ALL_RULES: list[dict] = [

    # ── 1. Ghost Pawn ──────────────────────────────────────────────────────────
    {
        "id": "ghost_pawn",
        "type": "on_move",
        "name": "Tốt Ma",
        "description": "Sau mỗi lần đi của Tốt, sinh thêm một Tốt ma trên ô ngẫu nhiên phía địch.",
        "apply": lambda board, move: None, # Handled in chess_engine.py
    },

    # ── 2. Double Step ─────────────────────────────────────────────────────────
    {
        "id": "double_step",
        "type": "passive",
        "name": "Bước Đôi",
        "description": "Tốt có thể đi 2 ô bất kể hàng nào (áp dụng qua logic engine).",
        "apply": lambda board, move: None,  # Handled in engine move generation
    },

    # ── 3. Knight Charge ───────────────────────────────────────────────────────
    {
        "id": "knight_charge",
        "type": "on_move",
        "name": "Mã Xung Phong",
        "description": "Mã khi ăn quân địch sẽ đi thêm một bước ngẫu nhiên hợp lệ.",
        "apply": lambda board, move: None, # Handled in chess_engine.py
    },

    # ── 4. Frozen Bishop ───────────────────────────────────────────────────────
    {
        "id": "frozen_bishop",
        "type": "instant",
        "name": "Tượng Đóng Băng",
        "description": "Một Tượng của đối thủ ngẫu nhiên bị loại khỏi bàn cờ trong 9 ply.",
        "apply": lambda board, move: (
            board.remove_piece_at(sq)
            if (pieces := _squares_of_piece(board, chess.BISHOP, board.turn))
            and (sq := random.choice(pieces))
            else None
        ),
    },

    # ── 5. Rook Teleport ───────────────────────────────────────────────────────
    {
        "id": "rook_teleport",
        "type": "instant",
        "name": "Xe Dịch Chuyển",
        "description": "Một Xe của bạn dịch chuyển tức thì đến ô ngẫu nhiên hợp lệ.",
        "apply": lambda board, move: (
            (
                board.remove_piece_at(src),
                board.set_piece_at(dst, chess.Piece(chess.ROOK, _opponent(board.turn)))
            )
            if (pieces := _squares_of_piece(board, chess.ROOK, _opponent(board.turn)))
            and (src := random.choice(pieces))
            and (dst := _random_empty_square(board))
            else None
        ),
    },

    # ── 6. Queen Aura ──────────────────────────────────────────────────────────
    {
        "id": "queen_aura",
        "type": "passive",
        "name": "Hào Quang Hậu",
        "description": "Mọi quân của bạn trong phạm vi 2 ô quanh Hậu không thể bị ăn (logic engine check).",
        "apply": lambda board, move: None,
    },

    # ── 7. Pawn Storm ──────────────────────────────────────────────────────────
    {
        "id": "pawn_storm",
        "type": "instant",
        "name": "Bão Tốt",
        "description": "Tất cả Tốt của bạn tiến thêm 1 ô (nếu đường trống).",
        "apply": lambda board, move: [
            board.set_piece_at(
                chess.square(chess.square_file(sq),
                             chess.square_rank(sq) + (1 if _opponent(board.turn) == chess.WHITE else -1)),
                chess.Piece(chess.PAWN, _opponent(board.turn))
            ) or board.remove_piece_at(sq)
            for sq in list(_squares_of_piece(board, chess.PAWN, _opponent(board.turn)))
            if 0 <= chess.square_rank(sq) + (1 if _opponent(board.turn) == chess.WHITE else -1) <= 7
            and board.piece_at(
                chess.square(chess.square_file(sq),
                             chess.square_rank(sq) + (1 if _opponent(board.turn) == chess.WHITE else -1))
            ) is None
        ],
    },

    # ── 8. Shadow King ─────────────────────────────────────────────────────────
    {
        "id": "shadow_king",
        "type": "passive",
        "name": "Vua Bóng Tối",
        "description": "Vua của bạn có thể di chuyển 2 ô theo chiều dọc / ngang trong 9 ply.",
        "apply": lambda board, move: None,
    },

    # ── 9. Explosive Pawn ──────────────────────────────────────────────────────
    {
        "id": "explosive_pawn",
        "type": "on_move",
        "name": "Tốt Bom",
        "description": "Khi Tốt của bạn bị ăn, nó phát nổ xóa mọi quân trong bán kính 1 ô.",
        "apply": lambda board, move: None, # Handled in chess_engine.py
    },

    # ── 10. Mirror Board ───────────────────────────────────────────────────────
    {
        "id": "mirror_board",
        "type": "passive",
        "name": "Bàn Gương",
        "description": "Bàn cờ được lật ngang (file a↔h) cho đến khi luật hết hiệu lực.",
        "apply": lambda board, move: None,  # Visual only, handled in frontend
    },

    # ── 11. Time Warp ──────────────────────────────────────────────────────────
    {
        "id": "time_warp",
        "type": "instant",
        "name": "Xuyên Thời Gian",
        "description": "Đồng hồ của đối thủ bị trừ 30 giây.",
        "apply": lambda board, move: None,  # Handled in timer logic
    },

    # ── 12. Swap Pieces ────────────────────────────────────────────────────────
    {
        "id": "swap_pieces",
        "type": "instant",
        "name": "Hoán Đổi Quân",
        "description": "Hai quân ngẫu nhiên của đối thủ (không phải Vua) bị hoán đổi vị trí.",
        "apply": lambda board, move: (
            (
                p1 := board.piece_at(sq1 := random.choice(
                    [s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == board.turn
                     and board.piece_at(s).piece_type != chess.KING]
                )),
                p2 := board.piece_at(sq2 := random.choice(
                    [s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == board.turn
                     and board.piece_at(s).piece_type != chess.KING
                     and s != sq1]
                )) if len([s for s in chess.SQUARES
                           if board.piece_at(s) and board.piece_at(s).color == board.turn
                           and board.piece_at(s).piece_type != chess.KING]) >= 2 else None,
                board.set_piece_at(sq1, p2) if p2 else None,
                board.set_piece_at(sq2, p1) if p2 else None,
            )
            if len([s for s in chess.SQUARES
                    if board.piece_at(s) and board.piece_at(s).color == board.turn
                    and board.piece_at(s).piece_type != chess.KING]) >= 2
            else None
        ),
    },

    # ── 13. Extra Queen ────────────────────────────────────────────────────────
    {
        "id": "extra_queen",
        "type": "instant",
        "name": "Hậu Bổ Sung",
        "description": "Bạn nhận thêm một Hậu đặt trên ô trống ngẫu nhiên.",
        "apply": lambda board, move: (
            board.set_piece_at(sq, chess.Piece(chess.QUEEN, _opponent(board.turn)))
            if (sq := _random_empty_square(board)) is not None
            else None
        ),
    },

    # ── 14. Blizzard ───────────────────────────────────────────────────────────
    {
        "id": "blizzard",
        "type": "passive",
        "name": "Bão Tuyết",
        "description": "Một cột ngẫu nhiên bị phong tỏa — không quân nào có thể vào/ra trong 3 ply.",
        "apply": lambda board, move: None,  # Enforced in engine legal move filter
    },

    # ── 15. Spy Rook ───────────────────────────────────────────────────────────
    {
        "id": "spy_rook",
        "type": "instant",
        "name": "Xe Gián Điệp",
        "description": "Một Xe của đối thủ bị 'chiếm' và trở thành quân của bạn.",
        "apply": lambda board, move: (
            (board.remove_piece_at(sq),
             board.set_piece_at(sq, chess.Piece(chess.ROOK, _opponent(board.turn))))
            if (pieces := _squares_of_piece(board, chess.ROOK, board.turn))
            and (sq := random.choice(pieces))
            else None
        ),
    },

    # ── 16. Poison Pawn ────────────────────────────────────────────────────────
    {
        "id": "poison_pawn",
        "type": "passive",
        "name": "Tốt Độc",
        "description": "Tốt đặc biệt — quân ăn nó sẽ bị xóa ngay lập tức.",
        "apply": lambda board, move: None,  # Tag handled in engine
    },

    # ── 17. Clone Knight ───────────────────────────────────────────────────────
    {
        "id": "clone_knight",
        "type": "instant",
        "name": "Mã Nhân Bản",
        "description": "Một Mã của bạn được nhân bản — sinh thêm một Mã ở ô lân cận trống.",
        "apply": lambda board, move: (
            board.set_piece_at(dst, chess.Piece(chess.KNIGHT, _opponent(board.turn)))
            if (pieces := _squares_of_piece(board, chess.KNIGHT, _opponent(board.turn)))
            and (src := random.choice(pieces))
            and (neighbors := [s for s in chess.SquareSet(chess.BB_KING_ATTACKS[src])
                               if board.piece_at(s) is None])
            and (dst := random.choice(neighbors))
            else None
        ),
    },

    # ── 18. Reverse Gravity ────────────────────────────────────────────────────
    {
        "id": "reverse_gravity",
        "type": "passive",
        "name": "Trọng Lực Ngược",
        "description": "Tất cả Tốt của đối thủ di chuyển ngược chiều trong 9 ply.",
        "apply": lambda board, move: None,  # Handled in engine pawn direction logic
    },

    # ── 19. Bishop Swap ────────────────────────────────────────────────────────
    {
        "id": "bishop_swap",
        "type": "instant",
        "name": "Tượng Đổi Chỗ",
        "description": "Hai Tượng của bạn (nếu có) hoán đổi vị trí với nhau.",
        "apply": lambda board, move: (
            (
                p1 := board.piece_at(sq1 := pieces[0]),
                p2 := board.piece_at(sq2 := pieces[1]),
                board.set_piece_at(sq1, p2),
                board.set_piece_at(sq2, p1),
            )
            if (pieces := _squares_of_piece(board, chess.BISHOP, _opponent(board.turn)))
            and len(pieces) >= 2
            else None
        ),
    },

    # ── 20. Fortify King ───────────────────────────────────────────────────────
    {
        "id": "fortify_king",
        "type": "passive",
        "name": "Vua Pháo Đài",
        "description": "Các ô xung quanh Vua của bạn được bảo vệ — quân địch không thể vào trong 9 ply.",
        "apply": lambda board, move: None,
    },

    # ── 21. Random Promotion ───────────────────────────────────────────────────
    {
        "id": "random_promotion",
        "type": "passive",
        "name": "Phong Cấp Ngẫu Nhiên",
        "description": "Khi Tốt phong cấp, loại quân được chọn ngẫu nhiên (không phải Vua).",
        "apply": lambda board, move: None,  # Handled in move processing
    },

    # ── 22. Dark Squares ───────────────────────────────────────────────────────
    {
        "id": "dark_squares",
        "type": "passive",
        "name": "Ô Tối",
        "description": "Tất cả quân trên ô đen (dark squares) bị ẩn khỏi đối thủ trong 9 ply.",
        "apply": lambda board, move: None,  # Visual only
    },

    # ── 23. Magnet ─────────────────────────────────────────────────────────────
    {
        "id": "magnet",
        "type": "instant",
        "name": "Nam Châm",
        "description": "Tất cả quân địch trên hàng 4-5 bị kéo về ô trung tâm gần nhất.",
        "apply": lambda board, move: [
            (board.remove_piece_at(sq),
             board.set_piece_at(center, board.piece_at(sq)))
            for sq in list(chess.SQUARES)
            if board.piece_at(sq) and board.piece_at(sq).color == board.turn
            and chess.square_rank(sq) in (3, 4)
            if not board.piece_at(center := min(
                [chess.D4, chess.D5, chess.E4, chess.E5],
                key=lambda c: chess.square_distance(sq, c)
            ))
        ],
    },

    # ── 24. Lucky Pawn ─────────────────────────────────────────────────────────
    {
        "id": "lucky_pawn",
        "type": "instant",
        "name": "Tốt May Mắn",
        "description": "Một Tốt ngẫu nhiên của bạn thăng cấp thành Hậu ngay lập tức.",
        "apply": lambda board, move: (
            (board.remove_piece_at(sq),
             board.set_piece_at(sq, chess.Piece(chess.QUEEN, _opponent(board.turn))))
            if (pieces := _squares_of_piece(board, chess.PAWN, _opponent(board.turn)))
            and (sq := random.choice(pieces))
            else None
        ),
    },

    # ── 25. Earthquake ─────────────────────────────────────────────────────────
    {
        "id": "earthquake",
        "type": "instant",
        "name": "Động Đất",
        "description": "3 quân ngẫu nhiên trên bàn (không phải Vua) bị dịch chuyển đến ô ngẫu nhiên.",
        "apply": lambda board, move: [
            (p := board.piece_at(sq),
             board.remove_piece_at(sq),
             board.set_piece_at(dst, p) if (dst := _random_empty_square(board)) else None)
            for sq in random.sample(
                [s for s in chess.SQUARES
                 if board.piece_at(s) and board.piece_at(s).piece_type != chess.KING],
                min(3, len([s for s in chess.SQUARES
                            if board.piece_at(s) and board.piece_at(s).piece_type != chess.KING]))
            )
        ],
    },

    # ── 26. Shield Wall ────────────────────────────────────────────────────────
    {
        "id": "shield_wall",
        "type": "passive",
        "name": "Tường Khiên",
        "description": "Hàng 2/7 của bạn không thể bị xâm nhập trong 9 ply.",
        "apply": lambda board, move: None,
    },

    # ── 27. Chaos ──────────────────────────────────────────────────────────────
    {
        "id": "chaos",
        "type": "instant",
        "name": "Hỗn Loạn",
        "description": "Tất cả quân không phải Vua bị xáo trộn vị trí ngẫu nhiên.",
        "apply": lambda board, move: (
            lambda pieces_and_squares: [
                board.set_piece_at(sq, p)
                for sq, p in zip(
                    random.sample(pieces_and_squares[0], len(pieces_and_squares[0])),
                    pieces_and_squares[1]
                )
            ]
        )(
            (
                [s for s in chess.SQUARES if board.piece_at(s) and board.piece_at(s).piece_type != chess.KING],
                [board.piece_at(s) for s in chess.SQUARES if board.piece_at(s) and board.piece_at(s).piece_type != chess.KING]
            )
        ),
    },

    # ── 28. Necromancer ────────────────────────────────────────────────────────
    {
        "id": "necromancer",
        "type": "passive",
        "name": "Pháp Sư Hồi Sinh",
        "description": "Một quân bị ăn gần nhất của bạn được hồi sinh trên ô trống ngẫu nhiên.",
        "apply": lambda board, move: None,  # Needs capture history from engine
    },

    # ── 29. Timestop ───────────────────────────────────────────────────────────
    {
        "id": "timestop",
        "type": "instant",
        "name": "Dừng Thời Gian",
        "description": "Đối thủ phải bỏ lượt tiếp theo (engine cưỡng chế null move).",
        "apply": lambda board, move: None,  # Handled in engine turn logic
    },

    # ── 30. Grand Exchange ─────────────────────────────────────────────────────
    {
        "id": "grand_exchange",
        "type": "instant",
        "name": "Đại Trao Đổi",
        "description": "Mỗi người chơi chọn một quân để hoán đổi màu (không phải Vua).",
        "apply": lambda board, move: (
            (
                sq1 := random.choice(
                    [s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == board.turn
                     and board.piece_at(s).piece_type != chess.KING]
                ),
                sq2 := random.choice(
                    [s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == _opponent(board.turn)
                     and board.piece_at(s).piece_type != chess.KING]
                ),
                p1 := board.piece_at(sq1),
                p2 := board.piece_at(sq2),
                board.set_piece_at(sq1, chess.Piece(p1.piece_type, _opponent(board.turn))),
                board.set_piece_at(sq2, chess.Piece(p2.piece_type, board.turn)),
            )
            if len([s for s in chess.SQUARES
                    if board.piece_at(s) and board.piece_at(s).color == board.turn
                    and board.piece_at(s).piece_type != chess.KING]) > 0
            and len([s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == _opponent(board.turn)
                     and board.piece_at(s).piece_type != chess.KING]) > 0
            else None
        ),
    },
]

# Build lookup dict for fast access by id
RULES_BY_ID: dict[str, dict] = {r["id"]: r for r in ALL_RULES}


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def get_random_rule_choices(active_ids: list[str], count: int = 3) -> list[dict]:
    """
    Trả về `count` luật ngẫu nhiên khác nhau và không trùng với các luật đang active.
    Trả list các dict {id, name, description, type}.
    """
    available = [r for r in ALL_RULES if r["id"] not in active_ids]
    sample = random.sample(available, min(count, len(available)))
    return [{"id": r["id"], "name": r["name"], "description": r["description"], "type": r.get("type", "passive")} for r in sample]


def apply_rule(rule_id: str, board: chess.Board, move: chess.Move) -> bool:
    """
    Áp dụng side-effect của luật lên board (sau khi move đã được push).
    Trả True nếu luật tồn tại, False nếu không.
    """
    rule = RULES_BY_ID.get(rule_id)
    if rule is None:
        return False
    try:
        rule["apply"](board, move)
    except Exception:
        pass  # Luật fail-safe: không crash game
    return True


def rule_info(rule_id: str) -> dict | None:
    """Trả dict {id, name, description, type} hoặc None."""
    r = RULES_BY_ID.get(rule_id)
    if r is None:
        return None
    return {"id": r["id"], "name": r["name"], "description": r["description"], "type": r.get("type", "passive")}


def all_rule_infos() -> list[dict]:
    """Trả danh sách tất cả luật (id, name, description, type)."""
    return [{"id": r["id"], "name": r["name"], "description": r["description"], "type": r.get("type", "passive")} for r in ALL_RULES]
