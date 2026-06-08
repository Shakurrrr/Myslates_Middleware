from rest_framework import serializers
from queue_app.models import SyncOperation


class SyncOperationSerializer(serializers.ModelSerializer):

    class Meta:
        model  = SyncOperation
        fields = [
            "id",
            "operation_type",
            "collection",
            "document_id",
            "payload",
            "client_timestamp",
            "idempotency_key",
            "user_id",
            "device_id",
        ]
        read_only_fields = ["id"]

    def validate_operation_type(self, value):
        if value not in ["CREATE", "UPDATE", "DELETE"]:
            raise serializers.ValidationError("Must be CREATE, UPDATE or DELETE")
        return value

    def validate_payload(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("payload must be a JSON object")
        return value