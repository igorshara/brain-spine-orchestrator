"""Gaussian-Process Bayesian Optimization for autonomous stimulation mapping.

GP-BO — визнаний SOTA-метод автономного підбору параметрів нейростимуляції
(Bonizzato et al. 2023, *Cell Reports Medicine*; GP-BO STAR Protocols 2024). Замість
перебору всіх конфігурацій (що клініка робить руками годинами) агент будує
ймовірнісну surrogate-модель відгуку й цілеспрямовано запитує найінформативніші
точки — і знаходить оптимум за ДЕСЯТКИ запитів замість сотень.

Тут реалізовано чистий GP (RBF-ядро) + acquisition (UCB) у numpy. Цінність, яку ми
демонструємо, — НЕ «точність на синтетиці» (це було б циркулярно), а
**sample-efficiency**: скільки запитів треба, щоб знайти оптимальну конфігурацію.
Це алгоритмічна властивість і реальна клінічна цінність (час клініциста).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


class GaussianProcess:
    """Minimal GP regressor with an RBF kernel (zero mean)."""

    def __init__(self, length_scale: float = 0.18, signal_var: float = 1.0,
                 noise: float = 0.02) -> None:
        self.l = length_scale
        self.sf = signal_var
        self.noise = noise

    def _kernel(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        d2 = np.sum(A**2, 1)[:, None] + np.sum(B**2, 1)[None, :] - 2 * A @ B.T
        return self.sf * np.exp(-0.5 * np.maximum(d2, 0) / self.l**2)

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        # Standardize targets so the kernel's unit signal variance is meaningful
        # (otherwise UCB's exploration term is mis-scaled).
        self.X = X
        self.y_mean = float(y.mean())
        self.y_std = float(y.std()) or 1.0
        self.y = (y - self.y_mean) / self.y_std
        K = self._kernel(X, X) + self.noise * np.eye(len(X))
        self.K_inv = np.linalg.inv(K)

    def predict(self, Xs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        Ks = self._kernel(Xs, self.X)
        mu = (Ks @ self.K_inv @ self.y) * self.y_std + self.y_mean
        var = (self.sf - np.einsum("ij,jk,ik->i", Ks, self.K_inv, Ks)) * self.y_std**2
        return mu, np.maximum(var, 1e-12)


def bayes_optimize(objective: Callable[[np.ndarray], float], candidates: np.ndarray,
                   n_init: int = 4, n_iter: int = 16, beta: float = 2.5, seed: int = 0):
    """UCB Gaussian-process Bayesian optimization over a discrete candidate set.

    candidates: (M, d) array of (normalized) parameter points. Returns the best
    value/point found and the best-so-far history (for regret curves)."""
    rng = np.random.default_rng(seed)
    init = list(rng.choice(len(candidates), n_init, replace=False))
    queried = list(init)
    X = candidates[init]
    y = np.array([objective(candidates[i]) for i in init])
    best_hist = [float(y.max())]
    for _ in range(n_iter):
        gp = GaussianProcess()
        gp.fit(X, y)
        mu, var = gp.predict(candidates)
        acq = mu + beta * np.sqrt(var)
        acq[queried] = -np.inf  # don't re-query
        nxt = int(np.argmax(acq))
        queried.append(nxt)
        X = np.vstack([X, candidates[nxt]])
        y = np.append(y, objective(candidates[nxt]))
        best_hist.append(float(y.max()))
    return {
        "best_value": float(y.max()),
        "best_index": int(np.argmax(y)),
        "history": best_hist,
        "n_queries": len(y),
        "queried": queried,
    }


def random_search(objective, candidates, n_queries: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(candidates))[:n_queries]
    best, hist = -np.inf, []
    for i in order:
        best = max(best, objective(candidates[i]))
        hist.append(float(best))
    return {"history": hist, "best_value": float(best)}


def queries_to_target(history, target: float) -> int:
    """First query index at which best-so-far reaches `target` (1-based)."""
    for i, v in enumerate(history):
        if v >= target:
            return i + 1
    return len(history)
