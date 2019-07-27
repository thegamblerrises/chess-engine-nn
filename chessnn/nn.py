import logging
import os
import time
from abc import abstractmethod

import numpy as np
from chess import PIECE_TYPES, square_file, square_rank
from tensorflow.python.keras import models, layers, utils, callbacks, regularizers

from chessnn import MoveRecord


class NN(object):
    _model: models.Model

    def __init__(self, filename=None) -> None:
        super().__init__()
        self._train_acc_threshold = 0.9
        self._validate_acc_threshold = 0.9
        if filename and os.path.exists(filename):
            logging.info("Loading model from: %s", filename)
            self._model = models.load_model(filename)
        else:
            logging.info("Starting with clean model")
            self._model = self._get_nn()
            self._model.summary(print_fn=logging.info)
            utils.plot_model(self._model, to_file=os.path.join(os.path.dirname(__file__), '..', 'model.png'),
                             show_shapes=True)

    def save(self, filename):
        logging.info("Saving model to: %s", filename)
        self._model.save(filename, overwrite=True)

    def inference(self, data):
        inputs, outputs = self._data_to_training_set(data, True)
        res = self._model.predict_on_batch(inputs)
        return [x[0] for x in res]

    def train(self, data, epochs, validation_data=None):
        logging.info("Preparing training set...")
        inputs, outputs = self._data_to_training_set(data, False)

        logging.info("Starting to learn...")
        cbs = [callbacks.TensorBoard('/tmp/tensorboard/%d' % time.time())] if epochs > 1 else []
        res = self._model.fit(inputs, outputs,  # sample_weight=np.array(sample_weights),
                              validation_split=0.1 if validation_data is None else 0.0, shuffle=True,
                              callbacks=cbs, verbose=2,
                              epochs=epochs, )
        logging.info("Trained: %s", {x: y[-1] for x, y in res.history.items()})

        if validation_data is not None:
            self.validate(validation_data)

        assert res.history['acc'][-1] >= self._train_acc_threshold, "Training has failed"
        if validation_data is None:
            assert res.history['val_acc'][-1] >= self._validate_acc_threshold

    def validate(self, data):
        logging.info("Preparing validation set...")
        inputs, outputs = self._data_to_training_set(data, False)

        logging.info("Starting to validate...")
        res = self._model.evaluate(inputs, outputs)
        logging.info("Validation loss and KPIs: %s", res)
        msg = "Validation accuracy is too low: %.3f < %s" % (res[1], self._validate_acc_threshold)
        assert res[1] >= self._validate_acc_threshold, msg

    @abstractmethod
    def _get_nn(self):
        pass

    @abstractmethod
    def _data_to_training_set(self, data, is_inference=False):
        pass


class NNChess(NN):
    def _get_nn(self):
        reg = regularizers.l2(0.00001)
        activ_hidden = "sigmoid"  # linear relu elu sigmoid tanh softmax
        activ_out = "softmax"  # linear relu elu sigmoid tanh softmax
        optimizer = "nadam"  # sgd rmsprop adagrad adadelta adamax adam nadam

        position = layers.Input(shape=(2, 8, 8, len(PIECE_TYPES)), name="position")

        main = layers.Flatten()(position)
        main = layers.Dense(100, activation=activ_hidden, kernel_regularizer=reg)(main)
        main = layers.Dense(100, activation=activ_hidden, kernel_regularizer=reg)(main)

        out_moves = layers.Dense(4096, activation=activ_out, name="moves")(main)
        out_eval = layers.Dense(2, activation=activ_out, name="eval")(main)

        outputs = [out_moves, out_eval]

        model = models.Model(inputs=[position, ], outputs=outputs)
        model.compile(optimizer=optimizer,
                      loss="categorical_crossentropy",
                      loss_weights=[1.0, 1.0],
                      metrics=['categorical_accuracy'])
        return model

    def _data_to_training_set(self, data, is_inference=False):
        batch_len = len(data)
        inputs_pos = np.full((batch_len, 2, 8, 8, len(PIECE_TYPES)), 0)

        evals = np.full((batch_len, 2), 0.0)
        out_from = np.full((batch_len, 8, 8), 0.0)
        out_to = np.full((batch_len, 8, 8), 0.0)

        pmoves = np.full((batch_len, 8, 8), 0.0)
        attacks = np.full((batch_len, 8, 8), 0.0)
        defences = np.full((batch_len, 8, 8), 0.0)
        threats = np.full((batch_len, 8, 8), 0.0)
        threatened = np.full((batch_len, 8, 8), 0.0)

        outputs = [evals, out_from, out_to] + [pmoves, attacks, defences, threats, threatened]

        batch_n = 0
        for rec in data:
            assert isinstance(rec, MoveRecord)
            score = rec.get_eval()
            assert score is not None

            evals[batch_n][0] = score
            evals[batch_n][1] = 1.0 - score
            inputs_pos[batch_n] = rec.position

            out_from[batch_n] = np.full((8, 8), 0.0 if score >= 0.5 else 1.0 / 64)
            out_to[batch_n] = np.full((8, 8), 0.0 if score >= 0.5 else 1.0 / 64)

            out_from[batch_n][square_file(rec.from_square)][square_rank(rec.from_square)] = 1 if score >= 0.5 else 0
            out_to[batch_n][square_file(rec.to_square)][square_rank(rec.to_square)] = 1 if score >= 0.5 else 0

            pmoves[batch_n] = rec.possible_moves
            attacks[batch_n] = rec.attacked
            defences[batch_n] = rec.defended
            threats[batch_n] = rec.threats
            threatened[batch_n] = rec.threatened

            batch_n += 1

        return [inputs_pos], outputs
