# engine/poller.py
from datetime import datetime, timezone
from config.firebase import get_firestore_client
from utils.django_client import DjangoAPIClient
from utils.logger import get_logger
from queue_app.models import SyncState

logger = get_logger(__name__)


class DjangoToFirestorePoller:
    """
    Polls Django sync endpoints for changes and pushes them to Firestore.
    Runs every 5 minutes via Celery beat.
    """

    # All collections to sync
    COLLECTIONS = [
        "users", "students", "teachers", "parents",
        "schools", "classes", "subjects", "topics",
        "assignments", "submissions",
        "attendance",
        "announcements", "results", "notifications",
        "achievements", "games",
        "chats", "communications", "discussions", "messages",
        "fees", "cbt_exams",
        "topic_progress", "student_xp",
    ]

    def __init__(self):
        self.db     = get_firestore_client()
        self.client = DjangoAPIClient.from_settings()

    def run(self) -> dict:
        """
        Main entry point. Polls all collections and syncs to Firestore.
        Returns a summary of what was synced.
        """
        summary = {"total": 0, "collections": {}}

        for collection in self.COLLECTIONS:
            try:
                count = self._sync_collection(collection)
                summary["collections"][collection] = count
                summary["total"] += count
            except Exception as e:
                logger.error(f"Failed to sync collection {collection}: {e}")
                summary["collections"][collection] = f"error: {e}"

        logger.info(f"Polling complete: {summary['total']} records synced across {len(self.COLLECTIONS)} collections")
        return summary

    def _sync_collection(self, collection: str) -> int:
        """
        Sync one collection from Django to Firestore.
        Returns the number of records synced.
        """
        # Get last sync timestamp for this collection
        state, _     = SyncState.objects.get_or_create(collection=collection)
        last_synced  = state.last_synced.isoformat() if state.last_synced else None

        if last_synced:
            logger.info(f"Polling {collection} for changes since {last_synced}")
        else:
            logger.info(f"First sync for {collection} — fetching all records")

        # Pull changes from Django
        records = self.client.get_changes(collection, updated_after=last_synced)

        if not records:
            logger.info(f"No changes in {collection}")
            return 0

        # Push each record to Firestore
        batch      = self.db.batch()
        batch_size = 0

        for record in records:
            doc_id = self._get_document_id(record, collection)
            if not doc_id:
                logger.warning(f"Skipping record in {collection} — no document ID found: {record}")
                continue

            ref = self.db.collection(collection).document(str(doc_id))

            if record.get("is_deleted"):
                batch.delete(ref)
            else:
                batch.set(ref, record, merge=True)

            batch_size += 1

            # Firestore batch limit is 500
            if batch_size >= 499:
                batch.commit()
                batch = self.db.batch()
                batch_size = 0

        if batch_size > 0:
            batch.commit()

        # Update last sync timestamp
        state.last_synced = datetime.now(timezone.utc)
        state.last_count  = len(records)
        state.save()

        logger.info(f"Synced {len(records)} records from {collection} to Firestore")
        return len(records)

    def _get_document_id(self, record: dict, collection: str) -> str | None:
        """
        Determine the Firestore document ID for a record.
        Uses firestore_id if available, falls back to Django id.
        """
        return (
            record.get("firestore_id") or
            record.get("id") or
            None
        )