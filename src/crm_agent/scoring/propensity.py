"""Conversion-propensity models (Strategy pattern).

* ``LogisticPropensityModel`` – a small, explainable logistic regression trained (with NumPy)
  on historical campaign outcomes. Used whenever history exists for a product.
* ``HeuristicPropensityModel`` – transparent weighted-signal scorer driven entirely by the
  ``signals`` block in ``config/products.json``. Used for products with no history (cold start).

Both return a probability **and** per-feature contributions, so every score can be explained
to the RM ("why this customer?") – a must-have for banking model-risk governance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import numpy as np

from crm_agent.scoring.features import FEATURE_LABELS, MODEL_FEATURES, NEGATIVE_LABELS


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def auc_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Rank-based ROC-AUC (Mann–Whitney U) – avoids a scikit-learn dependency."""
    order = np.argsort(y_score)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    pos = y_true == 1
    n_pos, n_neg = pos.sum(), (~pos).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


class PropensityModel(Protocol):
    name: str

    def predict(self, features: dict) -> tuple[float, dict[str, float]]:
        """Return (probability, contributions-by-feature)."""


class HeuristicPropensityModel:
    """p = sigmoid(bias + scale * S), where S = Σ wᵢ·signalᵢ / Σ positive wᵢ  ∈ [-1, 1].

    With the defaults a customer hitting half of the positive signal mass scores 50%,
    80% of it ≈ 86%, 30% of it ≈ 23% – a sensible, monotonic prior until real outcomes exist.
    """

    def __init__(self, product_id: str, signal_weights: dict[str, float], bias: float = -3.0, scale: float = 6.0):
        self.name = f"heuristic:{product_id}"
        self.weights = signal_weights
        self.bias = bias
        self.scale = scale
        self._norm = sum(w for w in signal_weights.values() if w > 0) or 1.0

    def predict(self, features: dict) -> tuple[float, dict[str, float]]:
        signals = features["signals"]
        contrib = {k: w * signals.get(k, 0.0) for k, w in self.weights.items()}
        z = self.bias + self.scale * sum(contrib.values()) / self._norm
        return float(_sigmoid(z)), contrib


class LogisticPropensityModel:
    def __init__(self, product_id: str, feature_names: list[str] | None = None):
        self.name = f"logistic:{product_id}"
        self.product_id = product_id
        self.feature_names = feature_names or list(MODEL_FEATURES)
        self.mean = self.std = self.weights = None
        self.bias = 0.0
        self.metrics: dict[str, float] = {}

    # -- training --------------------------------------------------------------------
    def fit(self, rows: list[dict], l2: float = 0.01, lr: float = 0.3, epochs: int = 600, seed: int = 7) -> "LogisticPropensityModel":
        X = np.array([[r[f] for f in self.feature_names] for r in rows], dtype=float)
        y = np.array([r["converted"] for r in rows], dtype=float)
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(X))
        split = int(0.8 * len(X))
        tr, te = idx[:split], idx[split:]

        self.mean = X[tr].mean(axis=0)
        self.std = X[tr].std(axis=0) + 1e-8
        Xs = (X - self.mean) / self.std
        w = np.zeros(X.shape[1])
        b = 0.0
        for _ in range(epochs):  # full-batch gradient descent
            p = _sigmoid(Xs[tr] @ w + b)
            err = p - y[tr]
            w -= lr * (Xs[tr].T @ err / len(tr) + l2 * w)
            b -= lr * err.mean()
        self.weights, self.bias = w, float(b)
        p_te = _sigmoid(Xs[te] @ w + b)
        self.metrics = {
            "train_rows": int(len(tr)), "test_rows": int(len(te)),
            "test_auc": round(auc_score(y[te], p_te), 3),
            "base_rate": round(float(y.mean()), 3),
        }
        return self

    # -- inference -------------------------------------------------------------------
    def predict(self, features: dict) -> tuple[float, dict[str, float]]:
        x = np.array([features["model_features"][f] for f in self.feature_names], dtype=float)
        xs = (x - self.mean) / self.std
        contrib_vec = self.weights * xs  # contribution relative to the average customer
        p = float(_sigmoid(contrib_vec.sum() + self.bias))
        return p, {f: float(c) for f, c in zip(self.feature_names, contrib_vec)}

    def coefficients(self) -> dict[str, float]:
        return {f: round(float(w), 3) for f, w in zip(self.feature_names, self.weights)}

    # -- persistence -----------------------------------------------------------------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "product_id": self.product_id, "feature_names": self.feature_names,
            "mean": self.mean.tolist(), "std": self.std.tolist(), "weights": self.weights.tolist(),
            "bias": self.bias, "metrics": self.metrics,
        }, indent=2))

    @classmethod
    def load(cls, path: Path) -> "LogisticPropensityModel":
        d = json.loads(path.read_text())
        m = cls(d["product_id"], d["feature_names"])
        m.mean, m.std, m.weights = np.array(d["mean"]), np.array(d["std"]), np.array(d["weights"])
        m.bias, m.metrics = d["bias"], d.get("metrics", {})
        return m


def explain(contributions: dict[str, float], top_n: int = 3) -> tuple[list[str], list[str]]:
    """Turn contributions into human-readable positive drivers and negative factors."""
    pos = [k for k, v in sorted(contributions.items(), key=lambda kv: kv[1], reverse=True) if v > 0.05][:top_n]
    neg = [k for k, v in sorted(contributions.items(), key=lambda kv: kv[1]) if v < -0.05][:2]
    pos_label = lambda k: FEATURE_LABELS.get(k, k.replace("_", " "))  # noqa: E731
    neg_label = lambda k: NEGATIVE_LABELS.get(k, pos_label(k))  # noqa: E731
    return [pos_label(k) for k in pos], [neg_label(k) for k in neg]


class PropensityModelRegistry:
    """Picks the best available model per product and caches trained models on disk."""

    def __init__(self, repository, products: dict, model_dir: Path):
        self.repo = repository
        self.products = products
        self.model_dir = Path(model_dir)
        self._cache: dict[str, PropensityModel] = {}

    def get(self, product_id: str) -> PropensityModel:
        if product_id in self._cache:
            return self._cache[product_id]
        model: PropensityModel
        path = self.model_dir / f"propensity_{product_id}.json"
        history = self.repo.get_campaign_history(product_id)
        if len(history) >= 200:
            if path.exists():
                model = LogisticPropensityModel.load(path)
            else:
                model = LogisticPropensityModel(product_id).fit(history)
                model.save(path)
        else:
            model = HeuristicPropensityModel(product_id, self.products[product_id]["signals"])
        self._cache[product_id] = model
        return model


def calibrate_monthly(prob: float, days_since_contact: int | None) -> float:
    """Light business adjustment: recent-contact fatigue reduces this month's odds."""
    if days_since_contact is not None and days_since_contact < 60:
        prob *= 0.85
    return float(min(0.99, max(0.01, prob)))


__all__ = ["HeuristicPropensityModel", "LogisticPropensityModel", "PropensityModelRegistry", "explain",
           "auc_score", "calibrate_monthly"]
