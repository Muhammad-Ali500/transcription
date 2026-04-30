import os
import asyncio
import logging
from datetime import timedelta
from functools import lru_cache
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


class MinioError(Exception):
    pass


class MinioUploadError(MinioError):
    pass


class MinioDownloadError(MinioError):
    pass


class MinioNotFoundError(MinioError):
    pass


class MinioService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
        except S3Error as e:
            logger.error(f"Failed to ensure bucket: {e}")
            raise MinioError(f"Bucket setup failed: {e}")

    def upload_file(self, file_path: str, object_name: str, content_type: str = "application/octet-stream") -> str:
        try:
            self.client.fput_object(
                self.bucket,
                object_name,
                file_path,
                content_type=content_type,
                metadata={"original-filename": os.path.basename(file_path)},
            )
            logger.info(f"Uploaded {file_path} -> {object_name}")
            return object_name
        except S3Error as e:
            logger.error(f"Upload failed: {e}")
            raise MinioUploadError(f"Upload failed: {e}")

    def upload_fileobj(self, file_obj, object_name: str, content_type: str = "application/octet-stream", file_size: int = None) -> str:
        try:
            size = file_size
            if size is None:
                file_obj.seek(0, 2)
                size = file_obj.tell()
                file_obj.seek(0)
            self.client.put_object(
                self.bucket,
                object_name,
                file_obj,
                length=size,
                content_type=content_type,
            )
            logger.info(f"Uploaded fileobj -> {object_name}")
            return object_name
        except S3Error as e:
            logger.error(f"Upload fileobj failed: {e}")
            raise MinioUploadError(f"Upload failed: {e}")

    def download_file(self, object_name: str, file_path: str) -> str:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            self.client.fget_object(self.bucket, object_name, file_path)
            logger.info(f"Downloaded {object_name} -> {file_path}")
            return file_path
        except S3Error as e:
            logger.error(f"Download failed: {e}")
            raise MinioDownloadError(f"Download failed: {e}")

    def get_file_url(self, object_name: str, expires: int = 3600) -> str:
        try:
            url = self.client.presigned_get_object(
                self.bucket, object_name, expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            logger.error(f"Presigned URL failed: {e}")
            raise MinioError(f"URL generation failed: {e}")

    def delete_file(self, object_name: str) -> bool:
        try:
            self.client.remove_object(self.bucket, object_name)
            logger.info(f"Deleted {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Delete failed: {e}")
            return False

    def list_files(self, prefix: str = "", recursive: bool = False) -> list[dict]:
        try:
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=recursive)
            return [
                {
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag,
                }
                for obj in objects
            ]
        except S3Error as e:
            logger.error(f"List files failed: {e}")
            raise MinioError(f"List failed: {e}")

    def file_exists(self, object_name: str) -> bool:
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False

    def get_file_info(self, object_name: str) -> dict:
        try:
            obj = self.client.stat_object(self.bucket, object_name)
            return {
                "size": obj.size,
                "content_type": obj.content_type,
                "last_modified": obj.last_modified,
                "metadata": obj.metadata,
            }
        except S3Error as e:
            logger.error(f"Get file info failed: {e}")
            raise MinioNotFoundError(f"Object not found: {object_name}")


@lru_cache()
def get_minio_service() -> MinioService:
    return MinioService()
