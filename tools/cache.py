import time
from typing import Any, Dict, Optional, Tuple

_store: Dict[str, Tuple[Any, float]] = {}
_TTL = 3600


def cache_get(key: str) -> Optional[Any]:
    if key in _store:
        value, ts = _store[key]
        if time.time() - ts < _TTL:
            return value
        del _store[key]
    return None


def cache_set(key: str, value: Any) -> None:
    _store[key] = (value, time.time())
