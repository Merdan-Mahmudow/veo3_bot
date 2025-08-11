import uuid
import boto3
from config import ENV

class YandexS3Storage():
    def __init__(self):
        self.settings = ENV()
        self.bucket = "veobot"
        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.settings.yc_s3_endpoint_url,
            aws_access_key_id=self.settings.yc_s3_access_key_id,
            aws_secret_access_key=self.settings.yc_s3_secret_access_key,
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except:
            self.s3.create_bucket(Bucket=self.bucket)

    def save(self, file_bytes: bytes, ext: str) -> None:
        filename = f"{uuid.uuid4()}{ext}"

        self.s3.put_object(
            Bucket=self.bucket,
            Key=filename,
            Body=file_bytes,
            StorageClass="COLD"
        )
        return f"https://storage.yandexcloud.net/{self.bucket}/{filename}"