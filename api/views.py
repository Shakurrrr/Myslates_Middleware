# api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from queue_app.models import SyncOperation
from api.serializers import SyncOperationSerializer
from utils.logger import get_logger

logger = get_logger(__name__)


class SubmitOperationView(APIView):

    def post(self, request):
        serializer = SyncOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        op = serializer.save(
            user_id   = request.data.get("user_id", "anonymous"),
            device_id = request.headers.get("X-Device-ID", ""),
        )

        try:
            from tasks.celery_tasks import process_single_op
            process_single_op.delay(str(op.id))
        except Exception as e:
            logger.warning(f"Could not queue async task: {e}")

        return Response(
            {"op_id": str(op.id), "status": "queued"},
            status=status.HTTP_202_ACCEPTED
        )


class BulkSubmitView(APIView):

    def post(self, request):
        ops_data = request.data.get("operations", [])
        if not ops_data:
            return Response({"error": "No operations provided"}, status=400)

        created_ids = []
        errors      = []

        for op_data in ops_data:
            serializer = SyncOperationSerializer(data=op_data)
            if serializer.is_valid():
                op = serializer.save(
                    user_id   = op_data.get("user_id", "anonymous"),
                    device_id = request.headers.get("X-Device-ID", ""),
                )
                created_ids.append(str(op.id))
            else:
                errors.append({"data": op_data, "errors": serializer.errors})

        try:
            from engine.sync_engine import SyncEngine
            SyncEngine().flush_pending()
        except Exception as e:
            logger.warning(f"Flush after bulk submit failed: {e}")

        return Response({
            "queued":   len(created_ids),
            "rejected": len(errors),
            "op_ids":   created_ids,
            "errors":   errors,
        }, status=status.HTTP_202_ACCEPTED)


class SyncStatusView(APIView):

    def get(self, request):
        op_ids = request.query_params.getlist("op_ids")
        ops    = SyncOperation.objects.filter(id__in=op_ids)
        return Response([
            {
                "op_id":   str(op.id),
                "status":  op.status,
                "retries": op.retry_count,
            }
            for op in ops
        ])