import hashlib
from django.core.cache import cache


class IdempotencyGuard:

    TTL = 60 * 60 * 24  # 24 hours

    def already_processed(self, idempotency_key: str) -> bool:
        try:
            return cache.get(self._make_key(idempotency_key)) is not None
        except Exception:
            return False

    def mark_processed(self, idempotency_key: str):
        try:
            cache.set(self._make_key(idempotency_key), "1", timeout=self.TTL)
        except Exception:
            pass

    def _make_key(self, idempotency_key: str) -> str:
        hashed = hashlib.sha256(idempotency_key.encode()).hexdigest()
        return f"idempotency:{hashed}"