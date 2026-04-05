from cachetools import TTLCache
from typing import Optional, Any, Dict

cache: TTLCache = TTLCache(maxsize=1000, ttl=300)  # type: ignore

def get_from_cache(key: str) -> Optional[Any]:
    return cache.get(key)

def set_in_cache(key: str, value: Any) -> None:
    cache[key] = value

def invalidate_cache(key: Optional[str] = None) -> None:
    if key:
        cache.pop(key, None)
    else:
        cache.clear()

def get_cache_stats() -> Dict[str, Any]:
    return {
        "size": len(cache),
        "maxsize": cache.maxsize,
        "ttl_seconds": cache.ttl
    }