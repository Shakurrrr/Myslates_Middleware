class SyncError(Exception):
    pass

class FirebaseUnavailableError(SyncError):
    pass

class ConflictResolutionError(SyncError):
    pass

class IdempotencyError(SyncError):
    pass

class DjangoAPIError(SyncError):
    pass