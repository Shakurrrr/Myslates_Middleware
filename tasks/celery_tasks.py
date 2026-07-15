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
    """Every 5 minutes: Django → Firestore"""
    from engine.poller import DjangoToFirestorePoller
    try:
        poller  = DjangoToFirestorePoller()
        summary = poller.run()
        logger.info(f"Django → Firestore complete: {summary}")
        return summary
    except Exception as exc:
        logger.error(f"Django → Firestore failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.celery_tasks.poll_firestore_to_django",
)
def poll_firestore_to_django(self):
    """Every 10 minutes: Firestore → Django"""
    from engine.firestore_poller import FirestoreToDjangoPoller
    try:
        poller  = FirestoreToDjangoPoller()
        summary = poller.run()
        logger.info(f"Firestore → Django complete: {summary}")
        return summary
    except Exception as exc:
        logger.error(f"Firestore → Django failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(name="tasks.celery_tasks.flush_pending_ops")
def flush_pending_ops():
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
