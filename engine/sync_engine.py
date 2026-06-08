# engine/sync_engine.py
import time
from datetime import datetime, timezone

from queue_app.models import SyncOperation, SyncLog
from engine.conflict_resolver import ConflictResolver
from engine.idempotency import IdempotencyGuard
from utils.logger import get_logger

logger = get_logger(__name__)


class SyncEngine:

    def __init__(self):
        self.conflict_resolver = ConflictResolver()
        self.idempotency_guard = IdempotencyGuard()

    def flush_pending(self, batch_size: int = 100) -> dict:
        ops = SyncOperation.objects.filter(
            status=SyncOperation.Status.PENDING
        ).select_for_update(skip_locked=True)[:batch_size]

        results = {"synced": 0, "failed": 0, "skipped": 0}
        for op in ops:
            outcome = self._process_single(op)
            results[outcome] += 1

        logger.info(f"Flush complete: {results}")
        return results

    def _process_single(self, op: SyncOperation) -> str:
        if self.idempotency_guard.already_processed(op.idempotency_key):
            op.status = SyncOperation.Status.SYNCED
            op.save(update_fields=["status"])
            return "skipped"

        op.status = SyncOperation.Status.IN_FLIGHT
        op.last_attempted = datetime.now(timezone.utc)
        op.save(update_fields=["status", "last_attempted"])

        start = time.time()
        try:
            self._sync_to_django(op)
            op.status = SyncOperation.Status.SYNCED
            op.save(update_fields=["status"])
            self._write_log(op, success=True, duration_ms=int((time.time() - start) * 1000))
            self.idempotency_guard.mark_processed(op.idempotency_key)
            return "synced"
        except Exception as e:
            return self._handle_failure(op, e, start)

    def _sync_to_django(self, op: SyncOperation):
        """
        Syncs a queued operation to the MySlates Django backend via REST API.
        Authenticates using the service account credentials in .env.
        """
        from utils.django_client import DjangoAPIClient
        client = DjangoAPIClient.from_settings()

        if op.operation_type == SyncOperation.OperationType.DELETE:
            client.delete(op.collection, op.document_id)

        elif op.operation_type == SyncOperation.OperationType.CREATE:
            client.create(op.collection, op.payload)

        elif op.operation_type == SyncOperation.OperationType.UPDATE:
            # Check for conflicts before updating
            try:
                existing = client.get(op.collection, op.document_id)
                payload  = self.conflict_resolver.resolve(
                    existing_doc = existing,
                    incoming_op  = op,
                )
                if payload is None:
                    logger.info(f"Op {op.id} discarded by conflict resolver")
                    return
            except Exception:
                # Document doesn't exist yet — just create it
                payload = op.payload

            client.update(op.collection, op.document_id, payload)

    def _handle_failure(self, op: SyncOperation, error: Exception, start: float) -> str:
        from django.conf import settings
        op.retry_count  += 1
        op.error_message = str(error)
        duration = int((time.time() - start) * 1000)

        if op.retry_count >= settings.SYNC_MAX_RETRIES:
            op.status = SyncOperation.Status.DEAD
            logger.error(f"Op {op.id} dead after {op.retry_count} retries: {error}")
        else:
            op.status = SyncOperation.Status.PENDING
            logger.warning(f"Op {op.id} failed attempt {op.retry_count}: {error}")

        op.save(update_fields=["status", "retry_count", "error_message"])
        self._write_log(op, success=False, error=str(error), duration_ms=duration)
        return "failed"

    def _write_log(self, op, success, error="", duration_ms=None):
        SyncLog.objects.create(
            operation     = op,
            success       = success,
            error_message = error,
            duration_ms   = duration_ms,
        )