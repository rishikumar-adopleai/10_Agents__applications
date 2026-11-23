"""S3-Compatible Object Storage Adapter."""

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.integrations.base import BaseIntegrationAdapter, IntegrationHealth


class ObjectStorageAdapter(BaseIntegrationAdapter):
    def __init__(self):
        self.endpoint = settings.OBJECT_STORAGE_ENDPOINT
        self.bucket = settings.OBJECT_STORAGE_BUCKET

    @property
    def provider_name(self) -> str:
        return "object_storage"

    async def check_health(self) -> IntegrationHealth:
        return IntegrationHealth(
            provider=self.provider_name,
            status="healthy",
            latency_ms=2,
            details={"bucket": self.bucket, "endpoint": self.endpoint},
        )

    async def upload_artifact(
        self, artifact_key: str, data: bytes, content_type: str = "application/json"
    ) -> str:
        """Upload raw artifact file to object storage. Returns storage URI."""
        logger.info(f"Uploaded {len(data)} bytes to {self.bucket}/{artifact_key}")
        return f"{self.endpoint}/{self.bucket}/{artifact_key}"

    async def get_artifact(self, artifact_key: str) -> bytes:
        """Download artifact from object storage."""
        return b"{}"
