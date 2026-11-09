from __future__ import annotations

import sys as _sys

_shim_name = __name__
_parent_name, _, _attr_name = _shim_name.rpartition(".")
from backend.fno.routes import flow as _module

globals().update(_module.__dict__)
_sys.modules[_shim_name] = _module
if _parent_name in _sys.modules:
    setattr(_sys.modules[_parent_name], _attr_name, _module)
