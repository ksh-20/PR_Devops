import threading
from models.handle_logging import get_logging_conf
logging = get_logging_conf()
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class _DataCache:
    _instance: Optional["_DataCache"] = None
    _instance_lock = threading.Lock()

    _lock: threading.RLock
    _store: dict[str, Any]
    _inflight: dict[str, threading.Event]
    _inflight_lock: threading.Lock

    def __new__(cls) -> "_DataCache":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._lock = threading.RLock()
                    instance._store = {}
                    instance._inflight = {}
                    instance._inflight_lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

    def get(self, key: str, default=None):
        with self._lock:
            return self._store.get(key, default)

    def set(self, key: str, value) -> None:
        with self._lock:
            self._store[key] = value
            logger.debug("[DataCache] Written key=%r (type=%s)", key, type(value).__name__)

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._store

    def get_or_fetch(self,key: str,fetch_fn: Callable[[], Any],*,timeout: float = 120.0,) -> Any:
        if self.has(key):
            return self.get(key)

        inflight_event: Optional[threading.Event] = None
        is_leader = False

        with self._inflight_lock:
            existing = self._inflight.get(key)
            if existing is not None:
                inflight_event = existing
            else:
                inflight_event = threading.Event()
                self._inflight[key] = inflight_event
                is_leader = True

        if not is_leader:
            inflight_event.wait(timeout=timeout)
            if self.has(key):
                return self.get(key)
            return {}

        try:
            if self.has(key):
                return self.get(key)

            result = fetch_fn()
            if result is not None:
                self.set(key, result)
                return result
            return {}
        except Exception as exc:
            logger.warning("[DataCache] get_or_fetch failed key=%r: %s", key, exc)
            return {}
        finally:
            with self._inflight_lock:
                self._inflight.pop(key, None)
            inflight_event.set()

    def keys(self) -> list:
        with self._lock:
            return list(self._store.keys())

    def stats(self) -> dict:
        with self._lock:
            return {
                "worker_status": self._store.get("worker_status", "not_started"),
                "last_sync_time": self._store.get("last_sync_time", None),
                "cached_keys": [k for k in self._store if k not in ("worker_status", "last_sync_time")],
            }


cache = _DataCache()