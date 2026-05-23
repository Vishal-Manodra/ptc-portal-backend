import boto3
from botocore.config import Config
from dotenv import load_dotenv
import os
import uuid
from datetime import datetime

load_dotenv()

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")


def get_r2_client():
    """
    Creates R2 client on demand instead of at startup.
    This way the app starts fine even if R2 isn't configured yet.
    """
    if not R2_ACCOUNT_ID or not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
        raise Exception(
            "R2 credentials not configured. "
            "Please fill in R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY in your .env file."
        )
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_file(file_bytes: bytes, original_filename: str, client_id: int) -> dict:
    ext = os.path.splitext(original_filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex[:8]}-{original_filename.replace(' ', '-').lower()}"
    today = datetime.now().strftime("%Y-%m")
    object_key = f"clients/{client_id}/{today}/{unique_name}"

    content_type_map = {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".csv": "text/csv",
        ".txt": "text/plain",
    }
    content_type = content_type_map.get(ext, "application/octet-stream")

    client = get_r2_client()
    client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=object_key,
        Body=file_bytes,
        ContentType=content_type,
    )

    file_url = f"{R2_PUBLIC_URL}/{object_key}"
    return {
        "file_url": file_url,
        "file_name": original_filename,
        "file_type": ext.lstrip("."),
        "file_size_kb": len(file_bytes) // 1024,
    }


def delete_file(file_url: str):
    if not file_url or not R2_PUBLIC_URL:
        return
    object_key = file_url.replace(f"{R2_PUBLIC_URL}/", "")
    client = get_r2_client()
    client.delete_object(Bucket=R2_BUCKET_NAME, Key=object_key)


def generate_presigned_url(file_url: str, expires_in_seconds: int = 3600) -> str:
    if not R2_PUBLIC_URL:
        return file_url
    object_key = file_url.replace(f"{R2_PUBLIC_URL}/", "")
    client = get_r2_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": object_key},
        ExpiresIn=expires_in_seconds,
    )