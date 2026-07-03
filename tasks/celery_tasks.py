# tasks/celery_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.celery_tasks.poll_django_to_firestore",
)
def poll_django_to_firestore(self):
    """
    Scheduled task: runs every 5 minutes.
    Polls Django for changes and pushes them to Firestore.
    """
    from engine.poller import DjangoToFirestorePoller
    try:
        poller  = DjangoToFirestorePoller()
        summary = poller.run()
        logger.info(f"Poll complete: {summary}")
        return summary
    except Exception as exc:
        logger.error(f"Poll task failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(name="tasks.celery_tasks.flush_pending_ops")
def flush_pending_ops():
    """
    Flush any manually queued operations (client → Django sync).
    """
    from engine.sync_engine import SyncEngine
    from django.conf import settings
    try:
        engine  = SyncEngine()
        results = engine.flush_pending(batch_size=settings.SYNC_BATCH_SIZE)
        logger.info(f"Flush complete: {results}")
        return results
    except Exception as exc:
        logger.error(f"Flush task failed: {exc}")


@shared_task(name="tasks.celery_tasks.retry_dead_letter")
def retry_dead_letter():
    from queue_app.models import SyncOperation
    dead_ops = SyncOperation.objects.filter(status=SyncOperation.Status.DEAD)
    count    = dead_ops.count()
    dead_ops.update(status=SyncOperation.Status.PENDING, retry_count=0)
    logger.warning(f"Revived {count} dead-letter operations")