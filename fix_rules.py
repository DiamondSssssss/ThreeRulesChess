import re

with open('backend/extra_rules.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix frozen_bishop
content = content.replace(
    '_squares_of_piece(board, chess.BISHOP, board.turn)',
    '_squares_of_piece(board, chess.BISHOP, _opponent(board.turn))',
    1
)

# Fix rook_teleport
content = content.replace(
    'chess.Piece(chess.ROOK, _opponent(board.turn))',
    'chess.Piece(chess.ROOK, board.turn)'
)
content = content.replace(
    '_squares_of_piece(board, chess.ROOK, _opponent(board.turn))',
    '_squares_of_piece(board, chess.ROOK, board.turn)',
    1 # first occurrence is in rook_teleport
)

# Fix pawn_storm: _opponent(board.turn) -> board.turn
pawn_storm_old = """    # ── 7. Pawn Storm ──────────────────────────────────────────────────────────
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
    },"""

pawn_storm_new = """    # ── 7. Pawn Storm ──────────────────────────────────────────────────────────
    {
        "id": "pawn_storm",
        "type": "instant",
        "name": "Bão Tốt",
        "description": "Tất cả Tốt của bạn tiến thêm 1 ô (nếu đường trống).",
        "apply": lambda board, move: [
            board.set_piece_at(
                chess.square(chess.square_file(sq),
                             chess.square_rank(sq) + (1 if board.turn == chess.WHITE else -1)),
                chess.Piece(chess.QUEEN if chess.square_rank(sq) + (1 if board.turn == chess.WHITE else -1) in (0, 7) else chess.PAWN, board.turn)
            ) or board.remove_piece_at(sq)
            for sq in list(_squares_of_piece(board, chess.PAWN, board.turn))
            if 0 <= chess.square_rank(sq) + (1 if board.turn == chess.WHITE else -1) <= 7
            and board.piece_at(
                chess.square(chess.square_file(sq),
                             chess.square_rank(sq) + (1 if board.turn == chess.WHITE else -1))
            ) is None
        ],
    },"""
content = content.replace(pawn_storm_old, pawn_storm_new)


# Fix swap_pieces
swap_pieces_old = """    # ── 12. Swap Pieces ────────────────────────────────────────────────────────
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
    },"""

swap_pieces_new = """    # ── 12. Swap Pieces ────────────────────────────────────────────────────────
    {
        "id": "swap_pieces",
        "type": "instant",
        "name": "Hoán Đổi Quân",
        "description": "Hai quân ngẫu nhiên của đối thủ (không phải Vua, không phải Tốt) bị hoán đổi vị trí.",
        "apply": lambda board, move: (
            (
                p1 := board.piece_at(sq1 := random.choice(
                    [s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == _opponent(board.turn)
                     and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)]
                )),
                p2 := board.piece_at(sq2 := random.choice(
                    [s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == _opponent(board.turn)
                     and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)
                     and s != sq1]
                )) if len([s for s in chess.SQUARES
                           if board.piece_at(s) and board.piece_at(s).color == _opponent(board.turn)
                           and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)]) >= 2 else None,
                board.set_piece_at(sq1, p2) if p2 else None,
                board.set_piece_at(sq2, p1) if p2 else None,
            )
            if len([s for s in chess.SQUARES
                    if board.piece_at(s) and board.piece_at(s).color == _opponent(board.turn)
                    and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)]) >= 2
            else None
        ),
    },"""
content = content.replace(swap_pieces_old, swap_pieces_new)


# Fix extra_queen
content = content.replace(
    'chess.Piece(chess.QUEEN, _opponent(board.turn))',
    'chess.Piece(chess.QUEEN, board.turn)',
    1 # first occurrence after swap_pieces is extra_queen
)

# Fix spy_rook
spy_rook_old = """    # ── 15. Spy Rook ───────────────────────────────────────────────────────────
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
    },"""

spy_rook_new = """    # ── 15. Spy Rook ───────────────────────────────────────────────────────────
    {
        "id": "spy_rook",
        "type": "instant",
        "name": "Xe Gián Điệp",
        "description": "Một Xe của đối thủ bị 'chiếm' và trở thành quân của bạn.",
        "apply": lambda board, move: (
            (board.remove_piece_at(sq),
             board.set_piece_at(sq, chess.Piece(chess.ROOK, board.turn)))
            if (pieces := _squares_of_piece(board, chess.ROOK, _opponent(board.turn)))
            and (sq := random.choice(pieces))
            else None
        ),
    },"""
content = content.replace(spy_rook_old, spy_rook_new)


# Fix clone_knight
clone_knight_old = """    # ── 17. Clone Knight ───────────────────────────────────────────────────────
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
    },"""

clone_knight_new = """    # ── 17. Clone Knight ───────────────────────────────────────────────────────
    {
        "id": "clone_knight",
        "type": "instant",
        "name": "Mã Nhân Bản",
        "description": "Một Mã của bạn được nhân bản — sinh thêm một Mã ở ô lân cận trống.",
        "apply": lambda board, move: (
            board.set_piece_at(dst, chess.Piece(chess.KNIGHT, board.turn))
            if (pieces := _squares_of_piece(board, chess.KNIGHT, board.turn))
            and (src := random.choice(pieces))
            and (neighbors := [s for s in chess.SquareSet(chess.BB_KING_ATTACKS[src])
                               if board.piece_at(s) is None])
            and (dst := random.choice(neighbors))
            else None
        ),
    },"""
content = content.replace(clone_knight_old, clone_knight_new)


# Fix push_back
push_back_old = """and (target := chess.square(chess.square_file(sq), chess.square_rank(sq) + (-1 if p_color == chess.WHITE else 1)))
            and 0 <= chess.square_rank(target) <= 7
            and board.piece_at(target) is None"""
push_back_new = """and (target := chess.square(chess.square_file(sq), chess.square_rank(sq) + (-1 if p_color == chess.WHITE else 1)))
            and 1 <= chess.square_rank(target) <= 6
            and board.piece_at(target) is None"""
content = content.replace(push_back_old, push_back_new)


# Fix bishop_swap
bishop_swap_old = """if (pieces := _squares_of_piece(board, chess.BISHOP, _opponent(board.turn)))"""
bishop_swap_new = """if (pieces := _squares_of_piece(board, chess.BISHOP, board.turn))"""
content = content.replace(bishop_swap_old, bishop_swap_new)


# Fix magnet
magnet_old = """if board.piece_at(sq) and board.piece_at(sq).color == board.turn"""
magnet_new = """if board.piece_at(sq) and board.piece_at(sq).color == _opponent(board.turn)"""
content = content.replace(magnet_old, magnet_new)


# Fix lucky_pawn
lucky_pawn_old = """    # ── 24. Lucky Pawn ─────────────────────────────────────────────────────────
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
    },"""

lucky_pawn_new = """    # ── 24. Lucky Pawn ─────────────────────────────────────────────────────────
    {
        "id": "lucky_pawn",
        "type": "instant",
        "name": "Tốt May Mắn",
        "description": "Một Tốt ngẫu nhiên của bạn thăng cấp thành Hậu ngay lập tức.",
        "apply": lambda board, move: (
            (board.remove_piece_at(sq),
             board.set_piece_at(sq, chess.Piece(chess.QUEEN, board.turn)))
            if (pieces := _squares_of_piece(board, chess.PAWN, board.turn))
            and (sq := random.choice(pieces))
            else None
        ),
    },"""
content = content.replace(lucky_pawn_old, lucky_pawn_new)


# Fix earthquake
earthquake_old = """    # ── 25. Earthquake ─────────────────────────────────────────────────────────
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
    },"""

earthquake_new = """    # ── 25. Earthquake ─────────────────────────────────────────────────────────
    {
        "id": "earthquake",
        "type": "instant",
        "name": "Động Đất",
        "description": "3 quân ngẫu nhiên trên bàn (không phải Vua, không phải Tốt) bị dịch chuyển đến ô ngẫu nhiên.",
        "apply": lambda board, move: [
            (p := board.piece_at(sq),
             board.remove_piece_at(sq),
             board.set_piece_at(dst, p) if (dst := _random_empty_square(board)) else None)
            for sq in random.sample(
                [s for s in chess.SQUARES
                 if board.piece_at(s) and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)],
                min(3, len([s for s in chess.SQUARES
                            if board.piece_at(s) and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)]))
            )
        ],
    },"""
content = content.replace(earthquake_old, earthquake_new)


# Fix chaos
chaos_old = """    # ── 27. Chaos ──────────────────────────────────────────────────────────────
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
    },"""

chaos_new = """    # ── 27. Chaos ──────────────────────────────────────────────────────────────
    {
        "id": "chaos",
        "type": "instant",
        "name": "Hỗn Loạn",
        "description": "Tất cả quân không phải Vua, không phải Tốt bị xáo trộn vị trí ngẫu nhiên.",
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
                [s for s in chess.SQUARES if board.piece_at(s) and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)],
                [board.piece_at(s) for s in chess.SQUARES if board.piece_at(s) and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)]
            )
        ),
    },"""
content = content.replace(chaos_old, chaos_new)

# Fix grand_exchange to exclude pawns
grand_exchange_old = """    # ── 30. Grand Exchange ─────────────────────────────────────────────────────
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
    },"""

grand_exchange_new = """    # ── 30. Grand Exchange ─────────────────────────────────────────────────────
    {
        "id": "grand_exchange",
        "type": "instant",
        "name": "Đại Trao Đổi",
        "description": "Mỗi người chơi chọn một quân để hoán đổi màu (không phải Vua, không phải Tốt).",
        "apply": lambda board, move: (
            (
                sq1 := random.choice(
                    [s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == board.turn
                     and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)]
                ),
                sq2 := random.choice(
                    [s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == _opponent(board.turn)
                     and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)]
                ),
                p1 := board.piece_at(sq1),
                p2 := board.piece_at(sq2),
                board.set_piece_at(sq1, chess.Piece(p1.piece_type, _opponent(board.turn))),
                board.set_piece_at(sq2, chess.Piece(p2.piece_type, board.turn)),
            )
            if len([s for s in chess.SQUARES
                    if board.piece_at(s) and board.piece_at(s).color == board.turn
                    and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)]) > 0
            and len([s for s in chess.SQUARES
                     if board.piece_at(s) and board.piece_at(s).color == _opponent(board.turn)
                     and board.piece_at(s).piece_type not in (chess.KING, chess.PAWN)]) > 0
            else None
        ),
    },"""
content = content.replace(grand_exchange_old, grand_exchange_new)

with open('backend/extra_rules.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done writing to extra_rules.py!")
