from utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)


class ConflictResolver:

    def resolve(self, existing_doc: dict, incoming_op) -> dict | None:
        try:
            return self._last_write_wins(existing_doc, incoming_op)
        except Exception as e:
            logger.error(f"Conflict resolution failed for op {incoming_op.id}: {e}")
            return incoming_op.payload

    def _last_write_wins(self, existing_doc: dict, incoming_op) -> dict | None:
        existing_ts = existing_doc.get("updated_at")
        incoming_ts = incoming_op.client_timestamp

        if existing_ts is None:
            return incoming_op.payload

        if hasattr(existing_ts, "tzinfo") and existing_ts.tzinfo is None:
            from datetime import timezone
            existing_ts = existing_ts.replace(tzinfo=timezone.utc)

        if incoming_ts > existing_ts:
            return incoming_op.payload
        else:
            logger.info(f"Existing doc wins — discarding stale op {incoming_op.id}")
            return None

    def _server_always_wins(self, existing_doc, incoming_op):
        return None

    def _client_always_wins(self, existing_doc, incoming_op):
        return incoming_op.payload

    def _merge_fields(self, existing_doc, incoming_op):
        return {**existing_doc, **incoming_op.payload}