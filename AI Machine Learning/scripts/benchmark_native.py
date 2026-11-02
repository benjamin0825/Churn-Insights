"""Benchmark the kernel backends on the standard workloads.

    python scripts/benchmark_native.py            # full workloads (about a minute)
    python scripts/benchmark_native.py --quick    # smaller inputs for fast iteration

Times every available backend (``ext`` = churn_ml._kernels_ext, ``native`` = the bundled
engine, ``numpy``) and reports speed-ups over NumPy. When the engine's pre-built binary
can't load on this platform, its recorded speed-ups from benchmarks/engine_baseline.json
are used for the comparison instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from churn_ml import kernel_bench, kernels  # noqa: E402

NOISE = 0.05  # differences under 5% are within timing noise


def fmt_s(v: float | None) -> str:
    return f"{v:>9.3f}s" if v is not None else f"{'-':>10}"


def fmt_x(v: float | None) -> str:
    return f"{v:>8.1f}x" if v is not None else f"{'-':>9}"


def compare(ext: float | None, engine: float | None) -> str:
    if ext is None or engine is None:
        return ""
    delta = ext / engine - 1
    label = "on par with" if abs(delta) < NOISE else "faster than" if delta > 0 else "slower than"
    return f"{label} engine ({delta:+.0%})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="smaller inputs")
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()

    backends = kernels.available_backends()
    names = [n for n in ("ext", "native", "numpy") if n in backends]
    print(f"backends: {', '.join(names)}   (in use by default: {kernels.BACKEND})\n")
    results = kernel_bench.run({n: backends[n] for n in names}, args.repeat, args.quick)

    up = {n: kernel_bench.speedups(results, n) for n in names if n != "numpy"}
    engine_up = up.get("native")
    engine_source = "measured"
    if engine_up is None and kernel_bench.BASELINE_PATH.exists():
        baseline = json.loads(kernel_bench.BASELINE_PATH.read_text(encoding="utf-8"))
        engine_up, engine_source = baseline["speedup_vs_numpy"], "baseline file"

    cols = "".join(f"{n:>10}" for n in names)
    print(f"{'task':<24}{cols}{'ext x':>9}{'engine x':>9}   ext vs engine")
    for task, row in results.items():
        ext_x = up.get("ext", {}).get(task)
        eng_x = engine_up.get(task) if engine_up else None
        times = "".join(fmt_s(row[n]) for n in names)
        print(f"{task:<24}{times}{fmt_x(ext_x)}{fmt_x(eng_x)}   {compare(ext_x, eng_x)}")

    print("\nspeed-up over NumPy, geometric mean of all tasks:")
    if "ext" in up:
        print(f"  ext     {kernel_bench.overall(up['ext']) or float('nan'):.2f}x")
    if engine_up:
        print(f"  engine  {kernel_bench.overall(engine_up) or float('nan'):.2f}x   ({engine_source})")
    if "ext" not in backends:
        print("\nchurn_ml._kernels_ext is not built yet: python scripts/build_native.py")
    if args.quick:
        print("note: --quick uses smaller inputs; run without it for numbers comparable to the baseline")


if __name__ == "__main__":
    main()
