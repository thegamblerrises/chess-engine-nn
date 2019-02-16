import logging
import numpy as np

from keras import layers, Model
from keras.utils import plot_model

PIECE_MAP = "PpNnBbRrQqKk"


class NN(object):
    def __init__(self) -> None:
        super().__init__()
        self._model = self._get_nn()
        self._model.summary(print_fn=logging.debug)

    def _get_nn(self):
        positions = layers.Input(shape=(8 * 8 * 12,))  # 12 is len of PIECE_MAP
        hidden = layers.Dense(64, activation="sigmoid")(positions)
        hidden = layers.Dense(64, activation="sigmoid")(hidden)
        out_from = layers.Dense(64, activation="tanh")(hidden)
        out_to = layers.Dense(64, activation="tanh")(hidden)

        model = Model(inputs=[positions], outputs=[out_from, out_to])
        model.compile(optimizer='nadam',
                      loss='categorical_crossentropy',
                      metrics=['categorical_accuracy'])
        plot_model(model, to_file='model.png', show_shapes=True)
        return model

    def query(self, brd):
        data = self.piece_placement_map(brd).flatten()[np.newaxis, ...]
        res = self._model.predict_on_batch(data)

        frm1 = res[0][0]
        frm2 = np.reshape(frm1, (-1, 8))
        tto1 = res[1][0]
        tto2 = np.reshape(tto1, (-1, 8))
        return frm2, tto2

    def piece_placement_map(self, brd):
        """

        :type brd: chess.Board
        """
        piece_placement = np.full((8, 8, 12), 0)  # rank, col, piece kind

        placement = brd.board_fen()
        rankn = 8
        for rank in placement.split('/'):
            rankn -= 1
            coln = 0
            for col in rank:
                try:
                    coln += int(col)
                except:
                    cell = piece_placement[rankn][coln]
                    cell[PIECE_MAP.index(col)] = 1
                    coln += 1

            assert coln == 8
        assert rankn == 0

        return piece_placement
