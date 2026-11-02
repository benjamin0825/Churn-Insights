"""Command-line interface.

    churn-ml [-c PROFILE] [--set key.path=value ...] <command> [options]

Commands
    simulate     generate the raw customer, usage, billing and ticket tables
    features     build (and cache) the labelled training snapshots
    train        tune, ensemble, calibrate, register and maybe promote a model
    score        batch-score every active customer with explanations
    monitor      drift report for a scoring week vs the training reference
    models       list registered model versions
    promote      promote a version to production
    rollback     restore the previous production version
    serve        start the REST API
    pipeline     simulate -> train -> score -> monitor in one go
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser

from .logging_utils import configure_logging, get_logger
from .settings import Settings, load_settings

log = get_logger("churn_ml")


def cmd_simulate(settings: Settings, args) -> None:
    from .data.validation import validate_raw
    from .training.dataset import simulate_and_save

    data = simulate_and_save(settings)
    report = validate_raw(data)
    print(
        json.dumps(
            {
                "saved_to": str(settings.raw_dir),
                **data.summary(),
                "validation_ok": report.ok,
                "warnings": report.warnings,
            },
            indent=2,
        )
    )


def cmd_features(settings: Settings, args) -> None:
    from .data.validation import validate_features
    from .training.dataset import build_training_frame, load_raw

    frame, spec = build_training_frame(
        settings, load_raw(settings, simulate_if_missing=True), use_cache=not args.rebuild
    )
    report = validate_features(frame, spec, require_label=True)
    print(
        json.dumps(
            {
                "rows": len(frame),
                "snapshots": int(frame["snapshot_week"].nunique()),
                "features": len(spec.model_inputs),
                **report.to_dict(),
            },
            indent=2,
        )
    )


def cmd_train(settings: Settings, args) -> None:
    from .training.trainer import train

    outcome = train(settings)
    board = outcome.leaderboard[["model", "weight", "val_roc_auc", "test_roc_auc", "test_average_precision"]]
    print("\n" + board.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    test = outcome.metrics["test"]
    print(
        f"\nRegistered v{outcome.version:04d} ({'promoted to production' if outcome.promoted else 'staging only'}): "
        f"{outcome.decision['reason']}"
    )
    print(
        f"Test ROC AUC {test['roc_auc']:.4f} | AP {test['average_precision']:.4f} | "
        f"lift@10% {test['lift_at_10pct']:.2f}x | profit ${test['campaign_profit']:,.0f}"
    )
    print(f"Report: {outcome.report_path}")
    if args.open:
        webbrowser.open(outcome.report_path.as_uri())


def cmd_score(settings: Settings, args) -> None:
    from .scoring import score_batch

    result = score_batch(settings, args.week, args.version, explain=not args.no_explain)
    print(result.scores.head(args.top).to_string(index=False))
    print(f"\n{len(result.scores):,} customers scored as of week {result.week} -> {result.path}")


def cmd_monitor(settings: Settings, args) -> None:
    from .scoring import monitor_batch, summarise

    result = monitor_batch(settings, args.week, args.version)
    print(summarise(result))
    print(f"Report: {result.html_path}")
    if args.open:
        webbrowser.open(result.html_path.as_uri())
    if args.fail_on_alert and result.report.status == "alert":
        sys.exit(2)


def cmd_models(settings: Settings, args) -> None:
    from .registry import ModelRegistry

    table = ModelRegistry(settings.registry_dir).list()
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}") if len(table) else "registry is empty")


def cmd_promote(settings: Settings, args) -> None:
    from .registry import ModelRegistry

    ModelRegistry(settings.registry_dir).promote(args.version, reason="manual promotion")
    print(f"v{args.version:04d} is now in production")


def cmd_rollback(settings: Settings, args) -> None:
    from .registry import ModelRegistry

    version = ModelRegistry(settings.registry_dir).rollback()
    print(f"rolled back: v{version:04d} is now in production")


def cmd_serve(settings: Settings, args) -> None:
    import uvicorn

    from .serving.api import create_app

    uvicorn.run(
        create_app(settings),
        host=args.host or settings.serving.host,
        port=args.port or settings.serving.port,
        log_level="info",
    )


def cmd_pipeline(settings: Settings, args) -> None:
    from .scoring import monitor_batch, score_batch, summarise
    from .training.dataset import simulate_and_save
    from .training.trainer import train

    simulate_and_save(settings)
    outcome = train(settings)
    print(f"\nv{outcome.version:04d} test ROC AUC {outcome.metrics['test']['roc_auc']:.4f} -> {outcome.report_path}")
    scored = score_batch(settings, None, outcome.version)
    print(f"scored {len(scored.scores):,} customers -> {scored.path}")
    monitored = monitor_batch(settings, None, outcome.version)
    print(summarise(monitored))
    print(f"drift report -> {monitored.html_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="churn-ml",
        description="Customer churn ML platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("-c", "--config", default=None, help="profile in configs/ (e.g. fast) or a YAML path")
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override any config value, e.g. --set tuning.n_trials.lightgbm=50",
    )
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("simulate", help="generate raw tables").set_defaults(func=cmd_simulate)

    p = sub.add_parser("features", help="build training snapshots")
    p.add_argument("--rebuild", action="store_true", help="ignore the feature cache")
    p.set_defaults(func=cmd_features)

    p = sub.add_parser("train", help="train, register and maybe promote")
    p.add_argument("--open", action="store_true", help="open the HTML report when done")
    p.set_defaults(func=cmd_train)

    for name, func, helptext in (
        ("score", cmd_score, "batch-score customers"),
        ("monitor", cmd_monitor, "drift report"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--week", type=int, default=None, help="as-of week (default: end of history)")
        p.add_argument("--version", default="production", help="model version, 'production' or 'latest'")
        if name == "score":
            p.add_argument("--top", type=int, default=15, help="rows to print")
            p.add_argument("--no-explain", action="store_true")
        else:
            p.add_argument("--open", action="store_true")
            p.add_argument("--fail-on-alert", action="store_true", help="exit with code 2 on drift alerts")
        p.set_defaults(func=func)

    sub.add_parser("models", help="list model versions").set_defaults(func=cmd_models)
    p = sub.add_parser("promote", help="promote a version")
    p.add_argument("version", type=int)
    p.set_defaults(func=cmd_promote)
    sub.add_parser("rollback", help="restore previous production model").set_defaults(func=cmd_rollback)

    p = sub.add_parser("serve", help="run the REST API")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.set_defaults(func=cmd_serve)

    sub.add_parser("pipeline", help="simulate, train, score and monitor").set_defaults(func=cmd_pipeline)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    configure_logging(args.log_level.upper())
    settings = load_settings(args.config, args.overrides)
    args.func(settings, args)


if __name__ == "__main__":
    main()
