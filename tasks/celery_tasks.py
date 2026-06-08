from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30, name="tasks.celery_tasks.flush_pending_ops")
def flush_pending_ops(self):
    from engine.sync_engine import SyncEngine
    from django.conf import settings
    try:
        engine  = SyncEngine()
        results = engine.flush_pending(batch_size=settings.SYNC_BATCH_SIZE)
        logger.info(f"Sync task complete: {results}")
        return results
    except Exception as exc:
        logger.error(f"Sync task failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(name="tasks.celery_tasks.process_single_op")
def process_single_op(operation_id: str):
    from engine.sync_engine import SyncEngine
    from queue_app.models import SyncOperation
    try:
        op     = SyncOperation.objects.get(id=operation_id)
        engine = SyncEngine()
        engine._process_single(op)
    except SyncOperation.DoesNotExist:
        logger.error(f"Operation {operation_id} not found")


@shared_task(name="tasks.celery_tasks.retry_dead_letter")
def retry_dead_letter():
    from queue_app.models import SyncOperation
    dead_ops = SyncOperation.objects.filter(status=SyncOperation.Status.DEAD)
    count    = dead_ops.count()
    dead_ops.update(status=SyncOperation.Status.PENDING, retry_count=0)
    logger.warning(f"Revived {count} dead-letter operations")