import logging
import sys

from chess import STARTING_FEN, Board, pgn, WHITE, BLACK

from nn import NN
from player import Player


def record_results(brd, rnd):
    journal = pgn.Game.from_board(brd)
    journal.headers.clear()
    journal.headers["White"] = "Lisa"
    journal.headers["Black"] = "Karen"
    journal.headers["Round"] = rnd
    journal.headers["Result"] = brd.result(claim_draw=True)
    if brd.is_checkmate():
        journal.end().comment = "checkmate"
    elif brd.can_claim_fifty_moves():
        journal.end().comment = "50 moves claim"
    elif brd.can_claim_threefold_repetition():
        journal.end().comment = "threefold claim"
    elif brd.is_insufficient_material():
        journal.end().comment = "insufficient material"
    elif not any(brd.generate_legal_moves()):
        journal.end().comment = "stalemate"
    else:
        journal.end().comment = "by other reason"

    # exporter = pgn.StringExporter(headers=True, variations=True, comments=True)
    # logging.info("\n%s", journal.accept(exporter))
    logging.info("Game #%d: %s by %s, %d moves", rnd, journal.headers["Result"], journal.end().comment,
                 brd.fullmove_number)
    with open("last.pgn", "w") as out:
        exporter = pgn.FileExporter(out)
        journal.accept(exporter)


def play_one_game(pwhite, pblack, rnd):
    board = Board(STARTING_FEN)
    pwhite.board = board
    pblack.board = board

    while pwhite.makes_move() and pblack.makes_move():  # and board.fullmove_number < 150
        logging.debug("%s. %s %s", board.fullmove_number - 1, board.move_stack[-1], board.move_stack[-2])

    record_results(board, rnd)


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    logging.basicConfig(level=logging.DEBUG)

    nn = NN("nn.hdf5")
    white = Player(WHITE, nn)
    black = Player(BLACK, nn)

    rnd = 1
    while True:
        play_one_game(white, black, rnd)
        nn.learn(white.get_moves() + black.get_moves())
        rnd += 1
