"""Residual-signal intent decoding — the middle path (no brain chip). Idea 4.

Між ручною кнопкою і дорогим імплантом у мозок — порожнеча. Багато пацієнтів мають
ЗАЛИШКОВІ волеві сигнали: sEMG частково збережених мʼязів, нахил тулуба, зміну
дихання під зусиллям, навіть евоковані відповіді самого стимулятора. Декодер
перекладає ці шумні сигнали в НАМІР (стояти/йти/стоп) і живить наш CPG — замикаючи
«думаю крок → крок» БЕЗ краніотомії, дешево й доступно.

Тут синтетичні залишкові сигнали (ILLUSTRATIVE); реальна версія — на справжніх
sEMG/IMU/сенсингу. Суть — довести, що серединний шлях декодування наміру працює і
деградує плавно зі зниженням «збереженості» сигналу.
"""

from __future__ import annotations

import numpy as np

INTENTS = ["idle", "stand", "walk"]
N_CH = 5  # residual channels: proximal EMG, rhythmic EMG, trunk lean, breathing, noise

# Class-conditional channel means (what each intent "looks like" in residual signals).
_MEANS = {
    "idle":  np.array([0.05, 0.05, 0.05, 0.05, 0.0]),
    "stand": np.array([0.70, 0.10, 0.35, 0.30, 0.0]),
    "walk":  np.array([0.75, 0.85, 0.55, 0.60, 0.0]),
}


class ResidualSignalModel:
    """Generates noisy residual signals for a given intent. `sparing` in (0,1]:
    1 = strong preserved signal, low = weak/ambiguous (more noise)."""

    def __init__(self, sparing: float = 0.6, seed: int = 0):
        self.sparing = sparing
        self.rng = np.random.default_rng(seed)

    def sample(self, intent: str) -> np.ndarray:
        noise = 0.12 + 0.6 * (1.0 - self.sparing)
        return _MEANS[intent] + self.rng.normal(0, noise, N_CH)

    def dataset(self, n_per_class: int = 200):
        X, y = [], []
        for k, it in enumerate(INTENTS):
            for _ in range(n_per_class):
                X.append(self.sample(it))
                y.append(k)
        return np.array(X), np.array(y)


class IntentDecoder:
    """Small classifier (numpy MLP, one-hot regression + argmax) + temporal
    smoothing. Maps residual signals -> intent in real time."""

    def __init__(self, n_hidden: int = 16, smooth: int = 5):
        from .distill import MLPRegressor
        self.net = MLPRegressor(N_CH, len(INTENTS), n_hidden=n_hidden, l2=1e-3)
        self.smooth = smooth
        self._hist: list[int] = []

    def fit(self, X, y, epochs: int = 2500):
        Y = np.eye(len(INTENTS))[y]
        self.net.fit(X, Y, epochs=epochs, lr=5e-3)
        return self

    def predict_raw(self, x) -> int:
        return int(np.argmax(self.net.forward(x.reshape(1, -1))[0]))

    def predict(self, x) -> int:
        """Temporally-smoothed decode (majority over a short window) — robust to
        single-sample noise at a small latency cost."""
        self._hist.append(self.predict_raw(x))
        self._hist = self._hist[-self.smooth:]
        return int(np.bincount(self._hist).argmax())

    def accuracy(self, X, y) -> float:
        pred = np.argmax(self.net.forward(X), axis=1)
        return float((pred == y).mean())


def decode_stream(decoder: IntentDecoder, model: ResidualSignalModel, timeline):
    """timeline: list of (intent, n_steps). Returns true vs smoothed-decoded labels
    and the mean lock-on latency (steps) after each intent change."""
    true, dec = [], []
    decoder._hist = []
    for it, n in timeline:
        for _ in range(n):
            true.append(INTENTS.index(it))
            dec.append(decoder.predict(model.sample(it)))
    true, dec = np.array(true), np.array(dec)
    # latency: steps from each change until the decode matches the new intent
    lat = []
    i = 1
    while i < len(true):
        if true[i] != true[i - 1]:
            j = i
            while j < len(true) and dec[j] != true[i]:
                j += 1
            lat.append(j - i)
            i = j + 1
        else:
            i += 1
    return true, dec, (float(np.mean(lat)) if lat else 0.0)
