import uuid
from django.db import models


class FirestoreCollection(models.TextChoices):
    SCHOOLS       = "schools"
    CLASSES       = "classes"
    SUBJECTS      = "subjects"
    TOPICS        = "topics"
    ASSIGNMENTS   = "assignments"
    SUBMISSIONS   = "submissions"
    ATTENDANCE    = "attendance"
    USERS         = "users"
    STUDENTS      = "students"
    TEACHERS      = "teachers"
    PARENTS       = "parents"
    CHATS         = "chats"
    MESSAGES      = "messages"
    DISCUSSIONS   = "discussions"
    ANNOUNCEMENTS = "announcements"
    RESULTS       = "results"
    NOTIFICATIONS = "notifications"
    ACHIEVEMENTS  = "achievements"
    GAMES         = "games"
    FEES          = "fees"
    CBT_EXAMS     = "cbt_exams"
    VIDEO_CLASSES = "video_classes"


class SyncOperation(models.Model):

    class OperationType(models.TextChoices):
        CREATE = "CREATE"
        UPDATE = "UPDATE"
        DELETE = "DELETE"

    class Status(models.TextChoices):
        PENDING   = "pending"
        IN_FLIGHT = "in_flight"
        SYNCED    = "synced"
        FAILED    = "failed"
        DEAD      = "dead"

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation_type   = models.CharField(max_length=10, choices=OperationType.choices)
    collection       = models.CharField(max_length=100, choices=FirestoreCollection.choices)
    document_id      = models.CharField(max_length=255)
    payload          = models.JSONField(default=dict)
    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    retry_count      = models.IntegerField(default=0)
    error_message    = models.TextField(blank=True)
    client_timestamp = models.DateTimeField()
    server_timestamp = models.DateTimeField(auto_now_add=True)
    user_id          = models.CharField(max_length=255)
    device_id        = models.CharField(max_length=255, blank=True)
    idempotency_key  = models.CharField(max_length=255, unique=True)
    last_attempted   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["client_timestamp"]
        indexes  = [
            models.Index(fields=["status", "client_timestamp"]),
            models.Index(fields=["collection", "document_id"]),
            models.Index(fields=["user_id", "status"]),
        ]

    def __str__(self):
        return f"{self.operation_type} {self.collection}/{self.document_id} [{self.status}]"


class SyncLog(models.Model):
    operation     = models.ForeignKey(SyncOperation, on_delete=models.CASCADE, related_name="logs")
    attempted_at  = models.DateTimeField(auto_now_add=True)
    success       = models.BooleanField()
    error_message = models.TextField(blank=True)
    duration_ms   = models.IntegerField(null=True)

    class Meta:
        ordering = ["-attempted_at"]

class SyncState(models.Model):
    """
    Tracks the last successful sync timestamp per collection.
    Used to determine what changed since the last poll.
    """
    collection   = models.CharField(max_length=100, unique=True)
    last_synced  = models.DateTimeField(null=True, blank=True)
    last_count   = models.IntegerField(default=0)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.collection} — last synced: {self.last_synced}"