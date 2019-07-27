import logging
from typing import List

import chess
import numpy as np

from chessnn import MoveRecord, BoardOptim, nn


class Player(object):
    moves_log: List[MoveRecord]
    board: BoardOptim
    nn: nn.NN

    def __init__(self, color, net) -> None:
        super().__init__()
        self.color = color
        # noinspection PyTypeChecker
        self.board = None
        self.start_from = (0, 0)
        self.nn = net
        self.moves_log = []

    def makes_move(self, in_round):
        pos = self.board.get_position() if self.color == chess.WHITE else self.board.mirror().get_position()

        move, geval = self._choose_best_move(pos)

        self.board.push(move)

        logging.debug("%d. %r %.2f\n%s", self.board.fullmove_number, move.uci(), geval, self.board.unicode())

        if move != chess.Move.null():
            piece = self.board.piece_at(move.to_square)
            log_rec = MoveRecord(position=pos, move=move, kpis=(), piece=piece.piece_type)
            log_rec.from_round = in_round
            log_rec.forced_eval = geval

            self.moves_log.append(log_rec)
            self.board.comment_stack.append(log_rec)

        not_over = move != chess.Move.null() and not self.board.is_game_over(claim_draw=True)
        return not_over

    def _choose_best_move(self, pos):
        scores4096, geval = self.nn.inference([[pos, 0.0, 0]])
        move = self._scores_to_move(scores4096)
        return move, geval[0]

    def _scores_to_move(self, scores_restored):
        cnt = 0
        for idx, score in sorted(enumerate(scores_restored), key=lambda x: -x[1]):
            move = chess.Move(idx // 64, idx % 64)
            if self.color == chess.BLACK:
                flipped = self._mirror_move(move)
                move = flipped

            if not self.board.is_legal(move):
                logging.debug("Invalid move suggested: %s", move)
                cnt += 1
                continue

            break
        else:
            logging.warning("No valid moves")
            move = chess.Move.null()
        logging.debug("Invalid moves skipped: %s", cnt)
        return move

    def get_moves(self):
        res = []
        for x in self.moves_log:
            res.append(x)
        self.moves_log.clear()
        return res

    def _mirror_move(self, move):
        """

        :type move: chess.Move
        """

        def flip(pos):
            arr = np.full((64,), False)
            arr[pos] = True
            arr = np.reshape(arr, (-1, 8))
            arr = np.flipud(arr)
            arr = arr.flatten()
            res = arr.argmax()
            return int(res)

        new_move = chess.Move(flip(move.from_square), flip(move.to_square), move.promotion, move.drop)
        return new_move
