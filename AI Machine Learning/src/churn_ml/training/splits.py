"""Out-of-time splitting with an embargo that mirrors real deployment.

A snapshot taken at week ``S`` only gets its label at ``S + horizon``. When
validating at week ``V`` we may therefore only train on snapshots with
``S + horizon <= V``; the same rule separates validation from test.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..settings import Settings


@dataclass(frozen=True)
class TemporalSplit:
    train_weeks: list[int]
    validation_weeks: list[int]
    test_weeks: list[int]
    embargoed_weeks: list[int]

    def describe(self) -> dict[str, list[int]]:
        return {
            "train": self.train_weeks,
            "validation": self.validation_weeks,
            "test": self.test_weeks,
            "embargoed": self.embargoed_weeks,
        }


def plan_split(weeks: list[int], horizon: int, n_validation: int, n_test: int) -> TemporalSplit:
    weeks = sorted(set(weeks))
    if len(weeks) < n_validation + n_test + 1:
        raise ValueError(f"need more than {n_validation + n_test} snapshots, got {len(weeks)}")
    test = weeks[-n_test:]
    val_pool = [w for w in weeks if w + horizon <= test[0]]
    validation = val_pool[-n_validation:]
    train = [w for w in weeks if w + horizon <= validation[0]]
    if not train:
        raise ValueError("no training snapshots left after the embargo; add history or shrink the horizon")
    used = set(train) | set(validation) | set(test)
    return TemporalSplit(train, validation, test, [w for w in weeks if w not in used])


def temporal_split(
    df: pd.DataFrame, settings: Settings
) -> tuple[TemporalSplit, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    plan = plan_split(
        df["snapshot_week"].unique().tolist(),
        settings.labeling.horizon_weeks,
        settings.split.validation_snapshots,
        settings.split.test_snapshots,
    )
    week = df["snapshot_week"]
    parts = [
        df[week.isin(w)].reset_index(drop=True) for w in (plan.train_weeks, plan.validation_weeks, plan.test_weeks)
    ]
    return plan, *parts
