"""
Lambda 1 — Presign URL
Returns a temporary S3 upload URL so the browser can PUT audio directly to S3.
Called by: GET /upload-url?ext=mp3
"""
import json, os, uuid
import boto3

s3     = boto3.client("s3")
BUCKET = os.environ["AUDIO_BUCKET"]

ALLOWED_EXTENSIONS = {"mp3", "mp4", "wav", "flac", "ogg", "m4a", "webm"}

def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    ext    = params.get("ext", "mp3").lower().lstrip(".")
    org_id = params.get("org_id", "default")

    if ext not in ALLOWED_EXTENSIONS:
        return _response(400, {"error": f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"})

    key          = f"raw-audio/{org_id}/{uuid.uuid4()}.{ext}"
    content_type = f"audio/{ext}"

    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=900,  # 15 minutes
    )

    return _response(200, {"upload_url": upload_url, "key": key, "expires_in": 900})


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
