"""PyTorch tabular network with categorical embeddings, wrapped as a scikit-learn classifier.

Input layout (produced by the ``ordinal`` preprocessor): ``[numeric..., text SVD..., categorical codes...]``
where the trailing ``n_categorical`` columns hold ordinal codes (``-1`` = unseen).
"""

from __future__ import annotations

import copy

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.model_selection import train_test_split
from sklearn.utils.validation import check_is_fitted

from .._runtime import import_torch

torch = import_torch()
nn = torch.nn


class TabularNet(nn.Module):
    def __init__(
        self,
        n_numeric: int,
        cardinalities: list[int],
        hidden_sizes: tuple[int, ...],
        dropout: float,
        embedding_max_dim: int,
    ):
        super().__init__()
        dims = [min(embedding_max_dim, (card + 1) // 2 + 1) for card in cardinalities]
        self.embeddings = nn.ModuleList(nn.Embedding(card, dim) for card, dim in zip(cardinalities, dims))
        self.embedding_dropout = nn.Dropout(dropout / 2)
        layers: list[nn.Module] = []
        width = n_numeric + sum(dims)
        for size in hidden_sizes:
            layers += [nn.Linear(width, size), nn.BatchNorm1d(size), nn.SiLU(), nn.Dropout(dropout)]
            width = size
        layers.append(nn.Linear(width, 1))
        self.mlp = nn.Sequential(*layers)

    def forward(self, numeric, categorical):
        parts = [numeric]
        if self.embeddings:
            embedded = torch.cat([emb(categorical[:, i]) for i, emb in enumerate(self.embeddings)], dim=1)
            parts.append(self.embedding_dropout(embedded))
        return self.mlp(torch.cat(parts, dim=1)).squeeze(1)


class TabularNNClassifier(ClassifierMixin, BaseEstimator):
    def __init__(
        self,
        n_categorical: int = 0,
        hidden_sizes: tuple[int, ...] = (256, 128),
        dropout: float = 0.2,
        lr: float = 1e-3,
        weight_decay: float = 1e-5,
        batch_size: int = 512,
        max_epochs: int = 40,
        patience: int = 5,
        validation_fraction: float = 0.1,
        embedding_max_dim: int = 16,
        random_state: int = 42,
        verbose: bool = False,
    ):
        self.n_categorical = n_categorical
        self.hidden_sizes = hidden_sizes
        self.dropout = dropout
        self.lr = lr
        self.weight_decay = weight_decay
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.validation_fraction = validation_fraction
        self.embedding_max_dim = embedding_max_dim
        self.random_state = random_state
        self.verbose = verbose

    # -------------------------------------------------------------- helpers
    def _split(self, X: np.ndarray):
        n_num = X.shape[1] - self.n_categorical
        numeric = torch.as_tensor(X[:, :n_num], dtype=torch.float32)
        codes = X[:, n_num:].astype(np.int64) + 1  # shift so 0 = unseen / missing
        if hasattr(self, "cardinalities_"):
            codes = np.where((codes < 0) | (codes >= np.asarray(self.cardinalities_)), 0, codes)
        return numeric, torch.as_tensor(codes, dtype=torch.long)

    def _batches(self, n: int, shuffle: bool, generator=None):
        order = torch.randperm(n, generator=generator) if shuffle else torch.arange(n)
        for start in range(0, n, self.batch_size):
            yield order[start : start + self.batch_size]

    # ------------------------------------------------------------------ API
    def fit(self, X, y):
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y).astype(np.float32).ravel()
        self.classes_ = np.array([0, 1])
        self.n_features_in_ = X.shape[1]
        torch.manual_seed(self.random_state)
        generator = torch.Generator().manual_seed(self.random_state)

        codes = X[:, X.shape[1] - self.n_categorical :].astype(np.int64) + 1
        self.cardinalities_ = [int(codes[:, j].max()) + 1 for j in range(self.n_categorical)]  # slot 0 = unseen

        X_tr, X_va, y_tr, y_va = train_test_split(
            X, y, test_size=self.validation_fraction, stratify=y, random_state=self.random_state
        )
        num_tr, cat_tr = self._split(X_tr)
        num_va, cat_va = self._split(X_va)
        target_tr, target_va = torch.as_tensor(y_tr), torch.as_tensor(y_va)

        model = TabularNet(
            num_tr.shape[1], self.cardinalities_, tuple(self.hidden_sizes), self.dropout, self.embedding_max_dim
        )
        optimizer = torch.optim.AdamW(model.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.5, patience=2)
        loss_fn = nn.BCEWithLogitsLoss()

        best_loss, best_state, stale = np.inf, None, 0
        self.history_ = []
        for epoch in range(self.max_epochs):
            model.train()
            running = 0.0
            for idx in self._batches(len(target_tr), shuffle=True, generator=generator):
                if len(idx) < 2:  # BatchNorm needs more than one row
                    continue
                optimizer.zero_grad()
                loss = loss_fn(model(num_tr[idx], cat_tr[idx]), target_tr[idx])
                loss.backward()
                optimizer.step()
                running += loss.item() * len(idx)
            model.eval()
            with torch.no_grad():
                val_loss = loss_fn(model(num_va, cat_va), target_va).item()
            scheduler.step(val_loss)
            self.history_.append({"epoch": epoch, "train_loss": running / len(target_tr), "val_loss": val_loss})
            if self.verbose:
                print(f"epoch {epoch:3d} train {running / len(target_tr):.4f} val {val_loss:.4f}")
            if val_loss < best_loss - 1e-4:
                best_loss, best_state, stale = val_loss, copy.deepcopy(model.state_dict()), 0
            else:
                stale += 1
                if stale >= self.patience:
                    break

        model.load_state_dict(best_state)
        self.model_ = model.eval()
        self.best_val_loss_ = best_loss
        return self

    def predict_proba(self, X):
        check_is_fitted(self, "model_")
        numeric, codes = self._split(np.asarray(X, dtype=np.float32))
        out = []
        with torch.no_grad():
            for idx in self._batches(len(numeric), shuffle=False):
                out.append(torch.sigmoid(self.model_(numeric[idx], codes[idx])).numpy())
        p = np.concatenate(out) if out else np.empty(0, dtype=np.float32)
        return np.column_stack([1 - p, p])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)
