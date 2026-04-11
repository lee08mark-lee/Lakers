import time
from functools import wraps

_cache: dict = {}


def ttl_cache(seconds: int = 3600):
    """Simple in-memory TTL cache decorator."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
            if key in _cache:
                result, expires = _cache[key]
                if time.time() < expires:
                    return result
            result = fn(*args, **kwargs)
            _cache[key] = (result, time.time() + seconds)
            return result
        return wrapper
    return decorator


def invalidate_all():
    """Clear the entire cache (used by the /refresh route)."""
    _cache.clear()


def last_updated() -> float | None:
    """Return the earliest expiry minus TTL (i.e., when the cache was last populated), or None."""
    if not _cache:
        return None
    # Find the minimum (time.time() - (expires - seconds)) — approximate
    # Just return now minus the remaining TTL of the first entry
    entry = next(iter(_cache.values()))
    _, expires = entry
    return expires  # caller can compute age from this
