# Tasks

## KRN-1: Open-source native kernel module (`churn_ml._kernels_ext`)

| | |
|---|---|
| **Area** | Performance / native code |
| **Language** | Cython (`.pyx`) or C (CPython C API) |
| **Python** | CPython 3.14 |
| **Time box** | _[fill in, e.g. 2 days]_ |
| **Deadline** | _[fill in]_ |
| **Spec** | [docs/native-kernels.md](docs/native-kernels.md) |

### Background

Feature engineering and drift monitoring run on six group-by and histogram kernels behind
[`src/churn_ml/kernels.py`](src/churn_ml/kernels.py). Today they're served by the bundled engine
`churn_ml._native` (pre-built binaries in `src/churn_ml/_native/`; source not included in this
repository) or by the pure-NumPy implementation `churn_ml._kernels_py`.

The engine only exists as binaries for one Python version on two platforms, and it can't be
maintained or extended here. We need a compiled implementation whose source lives in this repository.

### What to build

A compiled module **`churn_ml._kernels_ext`** implementing these six functions with exactly the
contract in [docs/native-kernels.md](docs/native-kernels.md#function-contract):

- `group_stats`
- `group_last`
- `group_max_where`
- `group_category_counts`
- `group_join`
- `binned_frequencies`

`kernels.py` picks up your module automatically once it's built (`ext` comes before `native` and `numpy`).

### Acceptance criteria

1. **Correct.** Results are identical to the `numpy` backend (`src/churn_ml/_kernels_py.py`) for
   every input, including the edge cases listed in the spec. `pytest` passes with
   `CHURN_ML_KERNELS=ext`.
2. **Fast.** Performance is at least on par with the bundled `native` engine on the standard
   workloads (`python scripts/benchmark_native.py`). Faster is better.
3. **Portable.** Builds with `python scripts/build_native.py` on Windows, Linux and macOS.
4. **Production quality.** Readable code; memory-safe (bad input must never cause out-of-bounds
   access); releases the GIL where it makes sense; no new runtime dependencies beyond NumPy.
5. **Non-breaking.** No changes to the public API in `kernels.py`, the behavior of
   `_kernels_py.py`, or the existing tests.

### Getting started

```powershell
# Python 3.14
python -m venv .venv
.\.venv\Scripts\Activate.ps1                  # Linux/macOS: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev,native]"                # includes Cython and the Zig C toolchain

# create src/churn_ml/_kernels_ext.pyx (or _kernels_ext.c), then:
python scripts/build_native.py                # -> src/churn_ml/_kernels_ext.<platform>.pyd / .so
python -c "import churn_ml.kernels as k; print(k.BACKEND)"   # prints 'ext' once it loads

pytest tests/test_kernels.py                  # every backend vs NumPy and pandas
$env:CHURN_ML_KERNELS = "ext"; pytest          # the whole suite on your module
python scripts/benchmark_native.py            # ext vs native engine vs numpy
```

No system C compiler is needed: `build_native.py` uses MSVC or gcc when available and falls back
to Zig (installed by the `native` extra) otherwise.

### Deliverables

Open a pull request containing:

1. **Your source file:** `src/churn_ml/_kernels_ext.pyx` or `src/churn_ml/_kernels_ext.c`.
   Don't commit compiled `.pyd`/`.so` files; `.gitignore` already excludes them.
2. **A design note** in the PR description covering:
   - your approach for each kernel and why it's fast,
   - benchmark output from `python scripts/benchmark_native.py` (full size, not `--quick`)
     and the machine you ran it on,
   - trade-offs, known limitations, and what you'd do next with more time.
3. **Tests** you added for cases you think are missing, if any (in a new test file; don't
   modify existing ones).

### Notes

- The spec in `docs/native-kernels.md` and the NumPy implementation are the source of truth.
  If they seem to disagree, follow `_kernels_py.py` and mention it in your note.
- Timing varies between runs; differences under ±5% are noise. Compare full-size runs.
- Questions about the requirements: _[fill in contact]_.
