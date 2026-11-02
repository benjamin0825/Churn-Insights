"""Render self-contained HTML reports (charts are embedded as data URIs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import __version__
from ..monitoring.drift import DriftReport
from . import charts

TEMPLATES = Path(__file__).parent / "templates"


def _thousands(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
    env.filters["thousands"] = _thousands
    return env


def _css() -> str:
    return (TEMPLATES / "base.css").read_text(encoding="utf-8")


def render_training_report(context: dict[str, Any]) -> str:
    ctx = dict(context)
    ctx.update(
        css=_css(),
        labels=charts.LABELS,
        package_version=__version__,
        params_json=json.dumps(ctx.get("best_params", {}), indent=2, default=str),
    )
    return _env().get_template("training_report.html.j2").render(**ctx)


def render_drift_report(report: DriftReport, week: int, version: int, warning: float, alert: float) -> str:
    counts = report.features["status"].value_counts().to_dict()
    payload = report.to_dict()
    return (
        _env()
        .get_template("drift_report.html.j2")
        .render(
            css=_css(),
            report=payload,
            week=week,
            version=version,
            warning=warning,
            alert=alert,
            counts={k: counts.get(k, 0) for k in ("alert", "warning", "stable")},
            chart=charts.psi_chart(report.features, warning, alert),
            package_version=__version__,
            segment_chart=(
                charts.psi_chart(report.segments, warning, alert, top=12, title="Drift within segments")
                if report.segments is not None
                else None
            ),
        )
    )
