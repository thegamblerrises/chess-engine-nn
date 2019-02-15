import logging

from objects import Board, STARTING_POSITION, Player

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    board = Board()
    board.from_fen(STARTING_POSITION)

    white = Player(board, 0)
    black = Player(board, 1)

    with open("last.pgn", "w") as out:
        while True:
            wmove = white.get_move()
            out.write("%d. %s " % (board.move_num, board.make_move(wmove)))
            out.flush()
            if not board.is_playable():
                break

            bmove = black.get_move()
            out.write("%s " % board.make_move(bmove))
            out.flush()
            if not board.is_playable():
                break
