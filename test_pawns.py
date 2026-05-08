import chess

board = chess.Board()

# test pawn storm for white
apply_storm = lambda board: [
    board.set_piece_at(
        chess.square(chess.square_file(sq),
                     chess.square_rank(sq) + (1 if board.turn == chess.WHITE else -1)),
        chess.Piece(chess.QUEEN if chess.square_rank(sq) + (1 if board.turn == chess.WHITE else -1) in (0, 7) else chess.PAWN, board.turn)
    ) or board.remove_piece_at(sq)
    for sq in list(board.pieces(chess.PAWN, board.turn))
    if 0 <= chess.square_rank(sq) + (1 if board.turn == chess.WHITE else -1) <= 7
    and board.piece_at(
        chess.square(chess.square_file(sq),
                     chess.square_rank(sq) + (1 if board.turn == chess.WHITE else -1))
    ) is None
]

board.turn = chess.WHITE
apply_storm(board)
print(board)
