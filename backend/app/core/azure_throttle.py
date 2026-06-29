import threading
import time
from models.handle_logging import get_logging_conf
logging = get_logging_conf()

logger = logging.getLogger(__name__)

MAX_CONCURRENT: int = 2      # max live Azure Cost API threads at once
TTL_SECONDS: int    = 300    # 5-minute success cache for date-range results
TOKEN_TTL: int      = 3300   # 55-minute token cache (tokens last 60 min)

class _AzureSemaphore:
    def __init__(self, limit: int = MAX_CONCURRENT):
        self._sem = threading.Semaphore(limit)
        self._lock = threading.Lock()
        self._active = 0

    def __enter__(self):
        self._sem.acquire()
        with self._lock:
            self._active += 1
        return self

    def __exit__(self, *_):
        with self._lock:
            self._active -= 1
        self._sem.release()

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active


azure_semaphore = _AzureSemaphore()


class _TtlCache:
    def __init__(self, ttl: int = TTL_SECONDS):
        self._ttl = ttl
        self._lock = threading.RLock()
        self._store: dict[str, tuple[float, object]] = {}  # key → (expires_at, value)

    def _prune(self):
        """Remove expired entries (called lazily on every read/write)."""
        now = time.monotonic()
        expired = [k for k, (exp, _) in self._store.items() if now >= exp]
        for k in expired:
            del self._store[k]

    def get(self, key: str):
        with self._lock:
            self._prune()
            entry = self._store.get(key)
            if entry is None:
                return None
            exp, val = entry
            if time.monotonic() >= exp:
                del self._store[key]
                return None
            return val

    def set(self, key: str, value) -> None:
        with self._lock:
            self._prune()
            self._store[key] = (time.monotonic() + self._ttl, value)
            logger.debug("[TtlCache] set key=%r (expires in %ds)", key, self._ttl)

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def stats(self) -> dict:
        with self._lock:
            self._prune()
            return {"entries": len(self._store), "ttl_seconds": self._ttl}


# Singleton instances
range_cache = _TtlCache(ttl=TTL_SECONDS)


class _TokenCache:
    def __init__(self, refresh_before_expiry: int = TOKEN_TTL):
        self._refresh_before = refresh_before_expiry
        self._lock = threading.RLock()
        self._store: dict[str, tuple[float, str]] = {}  # key → (expires_at, token)

    def _key(self, tenant_id: str, client_id: str) -> str:
        return f"{tenant_id}:{client_id}"

    def get(self, tenant_id: str, client_id: str) -> str | None:
        key = self._key(tenant_id, client_id)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            exp, token = entry
            if time.monotonic() >= exp:
                del self._store[key]
                logger.debug("[TokenCache] expired key=%r", key)
                return None
            return token

    def set(self, tenant_id: str, client_id: str, token: str) -> None:
        key = self._key(tenant_id, client_id)
        with self._lock:
            self._store[key] = (time.monotonic() + self._refresh_before, token)
            logger.debug("[TokenCache] cached token for key=%r (TTL=%ds)", key, self._refresh_before)


token_cache = _TokenCache()