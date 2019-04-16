import logging
import os
import pickle
import random
import sys
from typing import Set

from chess import STARTING_FEN, WHITE, BLACK

from chessnn import BoardOptim, MoveRecord, is_debug
from chessnn.nn import NN
from chessnn.player import Player


def play_one_game(pwhite, pblack, rnd, non_decisive_cnt=0):
    """

    :type pwhite: Player
    :type pblack: Player
    :type rnd: int
    """
    board = BoardOptim(STARTING_FEN)
    pwhite.board = board
    pwhite.start_from = (rnd % 20, non_decisive_cnt)
    pblack.board = board

    while True:  # and board.fullmove_number < 150
        if not pwhite.makes_move(rnd):
            break
        if not pblack.makes_move(rnd):
            break

    board.write_pgn(os.path.join(os.path.dirname(__file__), "last.pgn"), rnd)

    avg_score_w = sum([x.get_score() for x in pwhite.moves_log]) / float(len(pwhite.moves_log))
    avg_score_b = sum([x.get_score() for x in pblack.moves_log]) / float(len(pblack.moves_log))
    logging.info("Game #%d:\t%s by %s,\t%d moves,\t%.2f / %.2f AMS", rnd, board.result(claim_draw=True),
                 board.explain(), board.fullmove_number, avg_score_w, avg_score_b)

    return board.result(claim_draw=True)


class DataSet(object):
    def __init__(self, fname) -> None:
        super().__init__()
        self.fname = fname
        self.dataset = set()

    def dump_moves(self):
        if os.path.exists(self.fname):
            os.rename(self.fname, self.fname + ".bak")
        try:
            with open(self.fname, "wb") as fhd:
                pickle.dump(self.dataset, fhd)
        except:
            os.rename(self.fname + ".bak", self.fname)

    def load_moves(self):
        if os.path.exists(self.fname):
            with open(self.fname, 'rb') as fhd:
                loaded = pickle.load(fhd)
                self.dataset.update(loaded)

    def update(self, moves):
        lprev = len(self.dataset)
        self.dataset.update(moves)
        if len(self.dataset) - lprev < len(moves):
            logging.debug("partial increase")
        elif len(self.dataset) - lprev == len(moves):
            logging.debug("full increase")
        else:
            logging.debug("no increase")


def set_to_file(draw, param):
    lines = ["%s\n" % item for item in draw]
    lines.sort()
    with open(param, "w") as fhd:
        fhd.writelines(lines)


def play_with_score(pwhite, pblack):
    winning = DataSet("winning.pkl")
    winning.load_moves()
    losing = DataSet("losing.pkl")
    losing.load_moves()
    draw: Set[MoveRecord] = set()

    rnd = 0
    non_decisive_cnt = 0
    had_decisive = False
    while True:
        result = play_one_game(pwhite, pblack, rnd, non_decisive_cnt)

        wmoves = pwhite.get_moves()
        bmoves = pblack.get_moves()

        if result == '1-0':
            had_decisive = True
            for x, move in enumerate(wmoves):
                move.forced_score = float(x) / len(wmoves)
            winning.update(wmoves)
            losing.update(bmoves)
        elif result == '0-1':
            had_decisive = True
            for x, move in enumerate(bmoves):
                move.forced_score = float(x) / len(bmoves)
            winning.update(bmoves)
            losing.update(wmoves)
        else:
            draw.update(wmoves)
            draw.update(bmoves)

        rnd += 1
        if not (rnd % 20):
            winning.dataset -= losing.dataset
            # winning.dataset -= draw
            losing.dataset -= winning.dataset
            # losing.dataset -= draw

            if not had_decisive:
                non_decisive_cnt += 1
            else:
                non_decisive_cnt = 0

            while len(winning.dataset) > 10000:
                mmin = max([x.from_round for x in winning.dataset])
                for x in list(winning.dataset):
                    if x.from_round <= mmin:
                        winning.dataset.remove(x)

            logging.info("W: %s\tL: %s\tD: %s\tNon-dec: %s", len(winning.dataset), len(losing.dataset), len(draw),
                         non_decisive_cnt)

            # for x in winning.dataset:
            #    x.forced_score = 1.0

            # for x in losing.dataset:
            #    x.forced_score = 0.0

            winning.dump_moves()
            losing.dump_moves()
            dataset = winning.dataset  # | losing.dataset

            lst = list(draw)
            for x in lst:
                x.forced_score = 0  # random.random()
            random.shuffle(lst)
            dataset.update(lst[:10 * non_decisive_cnt])

            if had_decisive or not non_decisive_cnt % 5:
                nn.learn(dataset, 20)
                nn.save("nn.hdf5")

            draw = set()
            had_decisive = False


def play_per_turn(pwhite, pblack):
    dataset = DataSet("moves.pkl")
    dataset.load_moves()
    if not is_debug():
        pwhite.nn.learn(dataset.dataset, 20)
        nn.save("nn.hdf5")

    rnd = max([x.from_round for x in dataset.dataset]) if dataset.dataset else 0
    while True:
        result = play_one_game(pwhite, pblack, rnd)

        moves = pwhite.get_moves() + pblack.get_moves()
        moves = list(filter(lambda x: x.get_score() > 0, moves))
        dataset.update(moves)

        rnd += 1
        if not (rnd % 20):
            dataset.dump_moves()

            nn.learn(dataset.dataset, 20)
            nn.save("nn.hdf5")


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    mpl_logger = logging.getLogger('matplotlib')
    mpl_logger.setLevel(logging.WARNING)

    logging.basicConfig(level=logging.DEBUG if is_debug() else logging.INFO)

    nn = NN("nn.hdf5")
    white = Player(WHITE, nn)
    black = Player(BLACK, nn)

    # play_per_turn(white, black)
    play_with_score(white, black)
