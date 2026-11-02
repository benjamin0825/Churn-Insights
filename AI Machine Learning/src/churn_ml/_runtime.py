"""Platform fixes that must run before heavy native libraries are imported.

Recent PyTorch wheels for Windows link against a newer Microsoft C++ runtime
(14.40+, including ``vcruntime140_threads.dll``) than older Windows Server images
ship in System32. The ``msvc-runtime`` package drops current copies of those DLLs
into the virtual environment; loading them by absolute path first makes every
later load-by-name resolve to the newer copies, without touching the system.
"""

from __future__ import annotations

import ctypes
import os
import sys

_RUNTIME_DLLS = ("msvcp140.dll", "vcruntime140_threads.dll")
_done = False


def ensure_native_runtime() -> None:
    global _done
    if _done or os.name != "nt":
        return
    for name in _RUNTIME_DLLS:
        for folder in (sys.prefix, os.path.join(sys.prefix, "Scripts")):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                try:
                    ctypes.WinDLL(path)
                except OSError:
                    pass
                break
    _done = True


def import_torch():
    ensure_native_runtime()
    import torch

    return torch
