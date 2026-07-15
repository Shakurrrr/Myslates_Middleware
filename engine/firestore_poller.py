# engine/firestore_poller.py
from datetime import datetime, timezone
from google.cloud.firestore_v1 import FieldFilter
from config.firebase import get_firestore_client
from utils.django_client import DjangoAPIClient
from utils.logger import get_logger
from queue_app.models import SyncState

logger = get_logger(__name__)


class FirestoreToDjangoPoller:
    """
    Polls Firestore collections for changes and pushes them
    back to the MySlates Django backend every 10 minutes.
    """

    COLLECTIONS = [
        "users", "students", "teachers", "parents",
        "schools", "classes", "subjects", "topics",
        "assignments", "submissions",
        "attendance",
        "announcements", "results", "notifications",
        "achievements", "games",
        "chats", "communications", "discussions", "messages",
        "fees", "cbt_exams",
    ]

    BULK_SYNC_ENDPOINTS = {
        "users":          "/auth/users/bulk-sync/",
        "students":       "/auth/students/bulk-sync/",
        "teachers":       "/auth/teachers/bulk-sync/",
        "parents":        "/auth/parents/bulk-sync/",
        "schools":        "/academics/schools/bulk-sync/",
        "classes":        "/academics/classes/bulk-sync/",
        "subjects":       "/academics/subjects/bulk-sync/",
        "topics":         "/academics/topics/bulk-sync/",
        "assignments":    "/assignments/bulk-sync/",
        "submissions":    "/assignments/submissions/bulk-sync/",
        "attendance":     "/attendance/bulk-sync/",
        "announcements":  "/communication/announcements/bulk-sync/",
        "results":        "/communication/results/bulk-sync/",
        "notifications":  "/communication/notifications/bulk-sync/",
        "achievements":   "/gamification/achievements/bulk-sync/",
        "games":          "/gamification/games/bulk-sync/",
        "chats":          "/chat/chats/bulk-sync/",
        "communications": "/chat/communications/bulk-sync/",
        "discussions":    "/chat/discussions/bulk-sync/",
        "messages":       "/chat/messages/bulk-sync/",
        "fees":           "/modules/fees/bulk-sync/",
        "cbt_exams":      "/modules/cbt-exams/bulk-sync/",
    }

    def __init__(self):
        self.db     = get_firestore_client()
        self.client = DjangoAPIClient.from_settings()

    def run(self) -> dict:
        summary = {"total": 0, "collections": {}}

        for collection in self.COLLECTIONS:
            try:
                count = self._sync_collection(collection)
                summary["collections"][collection] = count
                summary["total"] += count
            except Exception as e:
                logger.error(f"Failed to sync {collection} from Firestore: {e}")
                summary["collections"][collection] = f"error: {e}"

        logger.info(f"Firestore → Django sync complete: {summary['total']} records")
        return summary

    def _sync_collection(self, collection: str) -> int:
        state_key   = f"firestore_{collection}"
        state, _    = SyncState.objects.get_or_create(collection=state_key)
        last_synced = state.last_synced

        col_ref = self.db.collection(collection)

        if last_synced:
            logger.info(f"Polling Firestore {collection} for changes since {last_synced}")
            docs = col_ref.where(
                filter=FieldFilter("updated_at", ">", last_synced)
            ).stream()
        else:
            logger.info(f"First Firestore sync for {collection} — fetching all")
            docs = col_ref.stream()

        records = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                # Ensure id is included
                if "id" not in data:
                    data["id"] = doc.id

                # Convert Firestore Timestamps to ISO strings
                data = self._serialize_record(data)
                records.append(data)

        if not records:
            logger.info(f"No Firestore changes in {collection}")
            return 0

        # Push to Django in batches of 100
        total_synced = 0
        for i in range(0, len(records), 100):
            batch        = records[i:i + 100]
            total_synced += self._push_to_django(collection, batch)

        state.last_synced = datetime.now(timezone.utc)
        state.last_count  = len(records)
        state.save()

        logger.info(f"Synced {total_synced} records from Firestore {collection} to Django")
        return total_synced

    def _serialize_record(self, data: dict) -> dict:
        """
        Convert Firestore Timestamp objects to ISO strings
        so they can be JSON serialized and sent to Django.
        """
        from google.cloud.firestore_v1 import base_document
        from google.protobuf.timestamp_pb2 import Timestamp

        serialized = {}
        for key, value in data.items():
            if hasattr(value, "isoformat"):
                # datetime object
                serialized[key] = value.isoformat()
            elif hasattr(value, "seconds") and hasattr(value, "nanos"):
                # Firestore Timestamp object
                dt = datetime.fromtimestamp(
                    value.seconds + value.nanos / 1e9,
                    tz=timezone.utc
                )
                serialized[key] = dt.isoformat()
            elif isinstance(value, dict):
                serialized[key] = self._serialize_record(value)
            elif isinstance(value, list):
                serialized[key] = [
                    self._serialize_record(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                serialized[key] = value
        return serialized

    def _push_to_django(self, collection: str, records: list) -> int:
        endpoint = self.BULK_SYNC_ENDPOINTS.get(collection)
        if not endpoint:
            logger.warning(f"No bulk-sync endpoint for: {collection}")
            return 0

        url = f"{self.client.base_url}{endpoint}"
        res = self.client.session.post(url, json={"records": records})

        if not res.ok:
            logger.error(f"Bulk sync failed for {collection} [{res.status_code}]: {res.text[:200]}")
            return 0

        data = res.json()
        logger.info(f"{collection}: created={data.get('created', 0)} updated={data.get('updated', 0)}")
        return data.get("synced", len(records))