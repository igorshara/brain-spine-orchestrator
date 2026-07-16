"""Distill the offline Moco optimum into a real-time policy (behavioral cloning).

Дистиляція: оптимальний (але повільний) розвʼязок OpenSim Moco перетворюємо на ШВИДКУ
real-time політику. Беремо пари «стан суглобів -> оптимальні м'язові збудження» з Moco-
розвʼязку і навчаємо малу нейромережу (numpy MLP, backprop+Adam) їх відтворювати —
це imitation learning / policy distillation з оптимального керування (надійніше за RL
з нуля). Результат — політика, що видає збудження за мікросекунди (придатна для
real-time контуру), без жодного солвера. Усе ILLUSTRATIVE.
"""

from __future__ import annotations

import json

import numpy as np


class MLPRegressor:
    """Small 1-hidden-layer tanh MLP with Adam — supervised regression in numpy."""

    def __init__(self, n_in, n_out, n_hidden=24, seed=0, l2=1e-4):
        rng = np.random.default_rng(seed)
        self.W1 = rng.normal(0, 0.3, (n_in, n_hidden))
        self.b1 = np.zeros(n_hidden)
        self.W2 = rng.normal(0, 0.3, (n_hidden, n_out))
        self.b2 = np.zeros(n_out)
        self.l2 = l2
        self._init_adam()

    def _init_adam(self):
        self._m = {k: np.zeros_like(getattr(self, k)) for k in ("W1", "b1", "W2", "b2")}
        self._v = {k: np.zeros_like(getattr(self, k)) for k in ("W1", "b1", "W2", "b2")}
        self._t = 0

    def forward(self, X):
        self._h = np.tanh(X @ self.W1 + self.b1)
        return self._h @ self.W2 + self.b2

    def fit(self, X, y, epochs=4000, lr=5e-3):
        for _ in range(epochs):
            pred = self.forward(X)
            err = pred - y
            n = len(X)
            gW2 = self._h.T @ err / n + self.l2 * self.W2
            gb2 = err.mean(0)
            dh = (err @ self.W2.T) * (1 - self._h**2)
            gW1 = X.T @ dh / n + self.l2 * self.W1
            gb1 = dh.mean(0)
            self._step({"W1": gW1, "b1": gb1, "W2": gW2, "b2": gb2}, lr)
        return self

    def _step(self, grads, lr, b1=0.9, b2=0.999, eps=1e-8):
        self._t += 1
        for k, g in grads.items():
            self._m[k] = b1 * self._m[k] + (1 - b1) * g
            self._v[k] = b2 * self._v[k] + (1 - b2) * g * g
            mh = self._m[k] / (1 - b1**self._t)
            vh = self._v[k] / (1 - b2**self._t)
            setattr(self, k, getattr(self, k) - lr * mh / (np.sqrt(vh) + eps))

    def params(self):
        return {k: getattr(self, k).tolist() for k in ("W1", "b1", "W2", "b2")}

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.params(), f)


def r2(y, p):
    ss_res = ((y - p) ** 2).sum()
    ss_tot = ((y - y.mean(0)) ** 2).sum()
    return 1 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
