import uuid
import boto3
from config import ENV

import uuid
from urllib.parse import urlparse, quote

import boto3
from botocore.exceptions import ClientError


class YandexS3Storage:
    def __init__(self):
        self.settings = ENV()
        self.bucket = "veobot"
        self.public_base = f"https://storage.yandexcloud.net/{self.bucket}"
        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.settings.yc_s3_endpoint_url,
            aws_access_key_id=self.settings.yc_s3_access_key_id,
            aws_secret_access_key=self.settings.yc_s3_secret_access_key,
        )
        # если бакет приватный — задай в ENV флаг yc_s3_public_bucket=False
        self.public_bucket = getattr(self.settings, "yc_s3_public_bucket", True)
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchBucket", "NotFound"):
                self.s3.create_bucket(Bucket=self.bucket)
            else:
                raise

    def save(self, file_bytes: bytes, extension: str, *, prefix: str = "", storage_class: str = "COLD") -> str:
        # поддержка extension и с точкой, и без
        if extension and not extension.startswith("."):
            extension = f".{extension}"
        filename = f"{uuid.uuid4()}{extension or ''}"
        key = f"{prefix}{filename}"

        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_bytes,
            StorageClass=storage_class,
        )
        # если бакет публичный — вернём постоянную ссылку
        return f"{self.public_base}/{quote(key)}"

    def get_file(
        self,
        key_or_url: str,
        *,
        expires_in: int = 3600,
        as_attachment: bool = False,
        download_name: str | None = None,
        force_presign: bool = False,
    ) -> str:
        """
        Возвращает ссылку на объект в бакете:
          - публичная постоянная ссылка (если бакет публичный и force_presign=False)
          - presigned URL с TTL (если бакет приватный или force_presign=True)

        key_or_url: ключ объекта (Key) или уже полный URL (из него извлечём Key).
        """
        key = self._extract_key(key_or_url)

        # Публичная ссылка без подписи
        if self.public_bucket and not force_presign:
            return f"{self.public_base}/{quote(key)}"

        # Подписанная ссылка (для приватного доступа или принудительно)
        params = {"Bucket": self.bucket, "Key": key}
        if as_attachment:
            fname = download_name or key.split("/")[-1]
            params["ResponseContentDisposition"] = f'attachment; filename="{fname}"'

        try:
            return self.s3.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            raise RuntimeError(f"Cannot presign URL for {key}: {e}") from e

    # --- helpers ---

    def _extract_key(self, key_or_url: str) -> str:
        """Нормализуем ключ: если пришёл URL — достаём Key из пути."""
        if key_or_url.startswith("http://") or key_or_url.startswith("https://"):
            parsed = urlparse(key_or_url)
            path = parsed.path.lstrip("/")  # 'bucket/key...'
            if path.startswith(f"{self.bucket}/"):
                return path[len(self.bucket) + 1 :]
            return path
        return key_or_url
