"""Optional compiled kernels for ``pip install``.

Metadata lives in pyproject.toml. Here we only declare ``churn_ml._kernels_ext`` when its
source exists (``src/churn_ml/_kernels_ext.pyx`` or ``_kernels_ext.c``; see
docs/native-kernels.md). The extension is ``optional``: installs without a C compiler still
succeed, and the package uses the bundled native engine or the NumPy kernels instead.
"""

from pathlib import Path

from setuptools import Extension, setup

pyx = Path("src/churn_ml/_kernels_ext.pyx")
c_file = pyx.with_suffix(".c")
extensions = []
if pyx.exists():
    try:
        from Cython.Build import cythonize

        extensions = cythonize([Extension("churn_ml._kernels_ext", [str(pyx)])], language_level=3, quiet=True)
    except ImportError:
        pass
elif c_file.exists():
    extensions = [Extension("churn_ml._kernels_ext", [str(c_file)])]

for ext in extensions:
    ext.optional = True

setup(ext_modules=extensions)
