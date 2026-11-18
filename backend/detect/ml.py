"""Unsupervised ML anomaly detectors (owner: P3).

All models are trained ONLY on normal operation (no attack or fault examples) and calibrated on separate held-out runs, so
the alert level is set by data rather than by hand. Scores are normalised so that 0 is the median of normal behaviour and
0.8 is the alert level (the 99.9th percentile of held-out scores plus a small margin), the same convention as every other
detector in the system.

Models (the same features go into each):
  IsolationForestModel : tree-based isolation. Weak when a single feature goes far out of range among many.
  PCAModel             : a linear autoencoder. Learns the normal relationships between signals and flags readings that
                         break them (reconstruction error). The best model on the validation attack runs.
  OneClassSVMModel     : a boundary around normal behaviour (RBF kernel).

Which model drives the live dashboard is decided in detect/bundle.py from validation attack runs, never from the test runs.
"""
from __future__ import annotations

import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM

from detect.features import FEATURE_LABELS, FEATURE_NAMES, INDEX

TOP_Z = 4.0  # a feature this many standard deviations from normal is worth naming
COUNT_FEATURES = {INDEX[n] for n in ("net_unauthorised", "net_events", "net_stale", "repeat_count", "n_open")}


class AnomalyModel:
    key = "model"
    label = "Model"

    def __init__(self, name: str | None = None, seed: int = 0) -> None:
        self.name = name or self.label
        self.seed = seed
        self.fitted = False

    # --- training ---------------------------------------------------------------------
    def fit(self, X_train: np.ndarray, val_runs: list[np.ndarray]) -> "AnomalyModel":
        """X_train: feature rows of normal training runs. val_runs: one matrix per held-out run, kept separate so the alert
        level can be set on the persistence-filtered scores the alert rule actually uses (two consecutive ticks)."""
        self.mu = X_train.mean(axis=0)
        sd = X_train.std(axis=0)
        floor = np.array([0.5 if i in COUNT_FEATURES else 1e-2 for i in range(len(self.mu))])
        self.sd = np.maximum(sd, floor)  # counts that are always zero in normal data must not explode the z-scores
        self._fit_model(X_train)
        raws = [self.raw(X) for X in val_runs]
        self.med = float(np.median(np.concatenate(raws)))
        persistent = np.concatenate([np.minimum(r[1:], r[:-1]) for r in raws])
        q = float(np.quantile(persistent, 0.999))
        self.thr = q + 0.25 * (q - self.med)  # a small margin above the 99.9th percentile of held-out data
        self.fitted = True
        return self

    def z(self, X: np.ndarray) -> np.ndarray:
        return np.clip((np.atleast_2d(X) - self.mu) / self.sd, -60.0, 60.0)

    def _fit_model(self, X: np.ndarray) -> None:
        raise NotImplementedError

    # --- scoring ----------------------------------------------------------------------
    def raw(self, X: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def score01(self, X: np.ndarray) -> np.ndarray:
        """0 at the median of normal, 0.8 at the alert level, capped at 1."""
        return np.clip(0.8 * (self.raw(X) - self.med) / (self.thr - self.med), 0.0, 1.0)

    def explain(self, x: np.ndarray, k: int = 2) -> list[tuple[str, float]]:
        """The features furthest from normal (z-scores against the training data): [(label, z), ...]."""
        z = self.z(x)[0]
        order = np.argsort(-np.abs(z))[:k]
        return [(FEATURE_LABELS[FEATURE_NAMES[i]], float(z[i])) for i in order]


class IsolationForestModel(AnomalyModel):
    key, label = "iforest", "Isolation Forest"

    def _fit_model(self, X):
        self.model = IsolationForest(n_estimators=200, max_samples=256, random_state=self.seed).fit(X)

    def raw(self, X):
        return -self.model.score_samples(np.atleast_2d(X))


class PCAModel(AnomalyModel):
    key, label = "pca", "Linear autoencoder (PCA)"

    def _fit_model(self, X):
        self.model = PCA(n_components=0.99, svd_solver="full").fit(self.z(X))

    def _residual(self, X):
        z = self.z(X)
        return z - self.model.inverse_transform(self.model.transform(z))

    def raw(self, X):
        return np.sqrt((self._residual(X) ** 2).sum(axis=1))

    def explain(self, x, k=2):
        """The signals that break the learned relationships the most (reconstruction error per feature)."""
        r = np.abs(self._residual(x)[0])
        order = np.argsort(-r)[:k]
        return [(FEATURE_LABELS[FEATURE_NAMES[i]], float(r[i])) for i in order]


class OneClassSVMModel(AnomalyModel):
    key, label = "ocsvm", "One-class SVM"

    def _fit_model(self, X):
        self.model = OneClassSVM(kernel="rbf", gamma="scale", nu=0.01).fit(self.z(X)[::3])

    def raw(self, X):
        return -self.model.score_samples(self.z(X))
