# engine/firestore_poller.py
from datetime import datetime, timezone
from google.cloud.firestore_v1 import FieldFilter, DocumentReference
from config.firebase import get_firestore_client
from utils.django_client import DjangoAPIClient
from utils.logger import get_logger
from queue_app.models import SyncState

logger = get_logger(__name__)


class FirestoreToDjangoPoller:
    """
    Polls Firestore collections for changes and pushes them
    back to the MySlates Django backend every 10 minutes.
    Only syncs collections that use integer IDs (Django-native).
    """

    COLLECTIONS = [
        "students", "teachers", "parents",
        "schools", "classes", "subjects", "topics",
        "assignments", "submissions",
        "attendance",
        "announcements", "results", "notifications",
        "fees", "cbt_exams",
    ]

    BULK_SYNC_ENDPOINTS = {
        "students":       "/auth/students/bulk/",
        "teachers":       "/auth/teachers/bulk/",
        "parents":        "/auth/parents/bulk/",
        "schools":        "/academics/schools/bulk/",
        "classes":        "/academics/classes/bulk/",
        "subjects":       "/academics/subjects/bulk/",
        "topics":         "/academics/topics/bulk/",
        "assignments":    "/assignments/bulk/",
        "submissions":    "/assignments/submissions/bulk/",
        "attendance":     "/attendance/bulk/",
        "announcements":  "/communication/announcements/bulk/",
        "results":        "/communication/results/bulk/",
        "notifications":  "/communication/notifications/bulk/",
        "fees":           "/modules/fees/bulk/",
        "cbt_exams":      "/modules/cbt-exams/bulk/",
    }

    def __init__(self):
        self.db     = get_firestore_client()
        self.client = DjangoAPIClient.from_settings()

    def run(self) -> dict:
        """
        Main entry point. Polls all Firestore collections
        and pushes changes to Django.
        """
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
        """
        Pull changed records from one Firestore collection
        and push them to Django via bulk endpoint.
        """
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
            if not data:
                continue

            if "id" not in data:
                data["id"] = doc.id

            serialized = self._serialize_record(data)

            # Skip records with non-integer IDs
            if serialized.get("_skip"):
                logger.warning(
                    f"Skipping record in {collection} with invalid id: {data.get('id')}"
                )
                continue

            records.append(serialized)

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
        Convert Firestore types to JSON-serializable Python types.
        - DocumentReferences → path strings
        - Timestamps → ISO strings
        - Non-integer IDs → mark for skipping
        """
        serialized = {}
        for key, value in data.items():
            if isinstance(value, DocumentReference):
                serialized[key] = value.path
            elif hasattr(value, "isoformat"):
                serialized[key] = value.isoformat()
            elif hasattr(value, "seconds") and hasattr(value, "nanos"):
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

        # Convert id to integer if possible
        if "id" in serialized:
            try:
                serialized["id"] = int(serialized["id"])
            except (ValueError, TypeError):
                serialized["_skip"] = True

        return serialized

    def _push_to_django(self, collection: str, records: list) -> int:
        """
        Send a batch of records to Django's bulk endpoint.
        """
        endpoint = self.BULK_SYNC_ENDPOINTS.get(collection)
        if not endpoint:
            logger.warning(f"No bulk endpoint for: {collection}")
            return 0

        url = f"{self.client.base_url}{endpoint}"
        res = self.client.session.post(url, json={"records": records})

        if not res.ok:
            logger.error(
                f"Bulk sync failed for {collection} "
                f"[{res.status_code}]: {res.text[:300]}"
            )
            return 0

        data = res.json()
        logger.info(
            f"{collection}: created={data.get('created', 0)} "
            f"updated={data.get('updated', 0)} "
            f"errors={data.get('errors', [])}"
        )
        return data.get("synced", len(records))