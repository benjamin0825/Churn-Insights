# Native kernel layer

Feature engineering and drift monitoring spend most of their time in six **group-by and
histogram kernels**: per-customer sums and means, "latest value", "last time something
happened", category counts, text concatenation and binned frequencies. All callers go
through [`src/churn_ml/kernels.py`](../src/churn_ml/kernels.py), which picks one of three
interchangeable backends:

| Backend | Module | Distribution | Notes |
|---|---|---|---|
| `ext` | `churn_ml._kernels_ext` | Built from source in this repo (`src/churn_ml/_kernels_ext.pyx` or `.c`) | **To be implemented** (see the work item below) |
| `native` | `churn_ml._native` | Pre-built binaries only; source isn't part of this repository | Current engine (see platforms below) |
| `numpy` | `churn_ml._kernels_py` | Pure Python/NumPy | Behavioral specification and portable fallback |

### Engine package (`src/churn_ml/_native/`)

The engine is a package of compiled submodules, one per concern, re-exported by `__init__.py`:

| Submodule | Functions |
|---|---|
| `_aggregate` | `group_stats`, `group_last` |
| `_select` | `group_max_where` |
| `_counting` | `group_category_counts` |
| `_text` | `group_join` |
| `_binning` | `binned_frequencies` |

**Requires CPython 3.14.** Each submodule ships pre-built for two platforms:

| Platform | Python | File pattern |
|---|---|---|
| Windows x64 | CPython 3.14 | `<submodule>.cp314-win_amd64.pyd` |
| Linux x86_64 (glibc 2.17+, manylinux2014) | CPython 3.14 | `<submodule>.cpython-314-x86_64-linux-gnu.so` |

On any other Python version or platform (for example Python 3.12, or macOS), the engine is
skipped and the `numpy` backend is used. Everything still works, just without the engine's
speed-up. Use **Python 3.14** to run with the engine.

`CHURN_ML_KERNELS=auto` (the default) uses `ext`, then `native`, then `numpy`, taking the first
that imports. Set it to `ext`, `native` or `numpy` to force a backend.

## Work item: open-source kernel module (`_kernels_ext`)

The bundled engine is binary-only. It's built for a single Python version (3.14) on two platforms
and can't be maintained in this repository. We need a compiled implementation whose source lives
here, so it can be built on any platform, reviewed and extended.

**Deliverable:** `src/churn_ml/_kernels_ext.pyx` (Cython) or `src/churn_ml/_kernels_ext.c` (CPython
C API) implementing the six functions below, plus a short design note in the pull request.

**Acceptance criteria**
1. **Identical results** to the `numpy` backend on all inputs, including the edge cases listed below.
   `pytest` must pass with `CHURN_ML_KERNELS=ext`.
2. **Performance at least on par with the `native` engine** on the standard workloads
   (`python scripts/benchmark_native.py`). Faster is better.
3. Builds with `python scripts/build_native.py` on Windows, Linux and macOS.
4. Production quality: readable, memory-safe (bad codes must never cause out-of-bounds access),
   releases the GIL where it makes sense, and adds no runtime dependencies beyond NumPy.
5. Don't change the public API in `kernels.py` or the behavior of `_kernels_py.py`; the rest of
   the codebase depends on both.

## Function contract

`kernels.py` converts inputs before calling a backend, so implementations always receive
C-contiguous arrays: `codes` is `int32`, values are `float64`, `mask` is `uint8`, `categories` is `int32`,
`texts` is a `list[str]`. A `codes` value of **-1 means "ignore this row"**. Rows arrive **in time order**.

| Function | Returns |
|---|---|
| `group_stats(codes, values[n, k], n_groups)` | `(sums[n_groups, k] float64, sums_of_squares[n_groups, k] float64, counts[n_groups] int64)`. NaN propagates into the sums. |
| `group_last(codes, values[n, k], n_groups)` | `float64[n_groups, k]`: values from each group's last row, NaN for groups without rows. |
| `group_max_where(codes, values[n], mask[n], n_groups)` | `float64[n_groups]`: max of `values` over rows where `mask` is set, NaN when none. Values may be negative. |
| `group_category_counts(codes, categories[n], n_groups, n_categories)` | `int64[n_groups, n_categories]`: rows per (group, category). Categories outside `0..n_categories-1` are ignored. |
| `group_join(codes, texts, n_groups, sep=" \| ")` | `object[n_groups]`: each group's strings joined with `sep` in row order, `""` when empty. |
| `binned_frequencies(values[n], edges[m])` | `float64[m + 2]`: share of values per bin. Bin `i` counts `edges[i-1] <= v < edges[i]` (as `searchsorted(..., side="right")`). The last slot is the share of NaN values. Raw zero counts when `n == 0`. |

Edge cases the callers rely on: empty inputs, groups with no rows, all rows ignored, values exactly
on a bin edge, duplicate edges, an empty `edges` array, NaN, non-ASCII text, and `n_groups` far
larger than the number of rows.

## Building, testing and benchmarking

```powershell
pip install -e ".[dev,native]"            # Cython + the Zig C toolchain (no Visual Studio needed)
python scripts/build_native.py            # -> src/churn_ml/_kernels_ext.<platform>.pyd / .so
python -c "import churn_ml.kernels as k; print(k.BACKEND)"   # 'ext' once it loads

pytest tests/test_kernels.py              # every available backend vs NumPy and pandas
$env:CHURN_ML_KERNELS = "ext"; pytest     # the whole suite on the new module
python scripts/benchmark_native.py        # ext vs native engine vs numpy
```

`benchmark_native.py` reports each backend's speed-up over NumPy on the same machine. Where the
engine's binary can't load (macOS, other Python versions or architectures), it compares against the engine
speed-ups recorded in [`benchmarks/engine_baseline.json`](../benchmarks/engine_baseline.json).
Differences under ±5% are within timing noise.
