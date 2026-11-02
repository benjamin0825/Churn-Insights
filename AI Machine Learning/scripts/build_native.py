"""Compile the open-source kernel module ``churn_ml._kernels_ext`` into a .pyd / .so.

    python scripts/build_native.py                 # src/churn_ml/_kernels_ext.pyx (or _kernels_ext.c)
    python scripts/build_native.py --zig           # force the Zig toolchain (pip install ziglang)
    python scripts/build_native.py --if-present    # exit quietly when there is no source (CI/Docker)
    python scripts/build_native.py --clean

Sources: ``_kernels_ext.pyx`` (Cython) is preferred; otherwise a hand-written
``_kernels_ext.c`` (CPython C API) is compiled as is. Strategy ``setuptools`` uses the
platform's normal compiler (gcc/clang, or MSVC on Windows); without one, ``zig cc`` is used.
Zig ships as a pip package, so nothing is installed system-wide.

The binary-only engine ``churn_ml._native`` is distributed pre-built and is not built here.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "churn_ml"
NAME = "_kernels_ext"
PYX, C_FILE = PKG / f"{NAME}.pyx", PKG / f"{NAME}.c"
OUTPUT = PKG / f"{NAME}{sysconfig.get_config_var('EXT_SUFFIX')}"
LEFTOVERS = [PKG / f"{NAME}.lib", PKG / f"{NAME}.pdb", OUTPUT.with_suffix(".lib"), OUTPUT.with_suffix(".pdb")]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def generate_c() -> bool:
    """Return True when the C file was generated from .pyx (and is therefore disposable)."""
    if PYX.exists():
        from Cython.Build import cythonize

        cythonize([str(PYX)], language_level=3, quiet=True, force=True)
        print(f"cythonized  {rel(PYX)} -> {rel(C_FILE)}")
        return True
    print(f"using hand-written C {rel(C_FILE)}")
    return False


def build_setuptools() -> None:
    from setuptools import Distribution, Extension
    from setuptools.command.build_ext import build_ext

    flags = ["/O2"] if sys.platform == "win32" else ["-O3"]
    ext = Extension(f"churn_ml.{NAME}", [str(C_FILE)], extra_compile_args=flags)
    dist = Distribution({"ext_modules": [ext], "script_name": "build_native.py"})
    cmd = build_ext(dist)
    cmd.build_lib = str(ROOT / "src")
    cmd.build_temp = str(ROOT / "build" / "native")
    cmd.ensure_finalized()
    cmd.run()


def build_zig() -> None:
    include = sysconfig.get_paths()["include"]
    cmd = [sys.executable, "-m", "ziglang", "cc", "-shared", "-O3", "-I", include, str(C_FILE), "-o", str(OUTPUT)]
    if sys.platform == "win32":
        version = f"{sys.version_info.major}{sys.version_info.minor}"
        cmd += ["-target", "x86_64-windows-gnu", "-L", str(Path(sys.base_prefix) / "libs"), f"-lpython{version}"]
    else:
        cmd += ["-fPIC"]
        if sys.platform == "darwin":
            cmd += ["-Wl,-undefined,dynamic_lookup"]
    subprocess.run(cmd, check=True, cwd=ROOT)


def verify() -> None:
    code = "import churn_ml.kernels as k; m = k.load_backend('ext'); print(m.__file__)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"built, but churn_ml.{NAME} does not import:\n{result.stderr}")
    print(f"verified    churn_ml.{NAME} imports")


def clean() -> None:
    targets = [OUTPUT, *LEFTOVERS] + ([C_FILE] if PYX.exists() else [])  # never delete hand-written C
    for path in targets:
        path.unlink(missing_ok=True)
    shutil.rmtree(ROOT / "build" / "native", ignore_errors=True)
    print(f"cleaned {NAME} build outputs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zig", action="store_true", help="use zig cc instead of the setuptools compiler")
    parser.add_argument("--if-present", action="store_true", help="succeed without building when no source exists")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    if args.clean:
        clean()
        return
    if not PYX.exists() and not C_FILE.exists():
        message = f"no source found: create {rel(PYX)} or {rel(C_FILE)} (see docs/native-kernels.md)"
        if args.if_present:
            print(f"skipped     {message}")
            return
        raise SystemExit(message)

    generate_c()
    if args.zig:
        build_zig()
    else:
        try:
            build_setuptools()
        except Exception as exc:  # no compiler: MSVC missing, gcc missing, ...
            print(f"setuptools compiler unavailable ({type(exc).__name__}: {str(exc).splitlines()[0]}); trying zig")
            build_zig()
    for leftover in LEFTOVERS:
        leftover.unlink(missing_ok=True)
    print(f"built       {rel(OUTPUT)} ({OUTPUT.stat().st_size // 1024} KB)")
    verify()


if __name__ == "__main__":
    main()
