from django.urls import path
from api.views import SubmitOperationView, BulkSubmitView, SyncStatusView

urlpatterns = [
    path("sync/submit/", SubmitOperationView.as_view(), name="sync-submit"),
    path("sync/bulk/",   BulkSubmitView.as_view(),     name="sync-bulk"),
    path("sync/status/", SyncStatusView.as_view(),     name="sync-status"),
]