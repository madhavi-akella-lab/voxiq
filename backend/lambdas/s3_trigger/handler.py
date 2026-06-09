"""
Lambda 2 — S3 Trigger → AWS Transcribe
Fires automatically when an audio file lands in the raw-audio/ prefix.
Starts a Transcribe job and writes a TRANSCRIBING record to DynamoDB.
"""
import json, os, re, urllib.parse
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

import boto3

transcribe = boto3.client("transcribe")
dynamodb   = boto3.resource("dynamodb")
TABLE      = os.environ["DYNAMODB_TABLE"]
RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]
LANGUAGE_CODE  = os.environ.get("LANGUAGE_CODE", "en-US")

SUPPORTED = {"mp3","mp4","wav","flac","ogg","amr","webm","m4a"}


def lambda_handler(event, context):
    results = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key    = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        print(f"New audio: s3://{bucket}/{key}")
        result = process(bucket, key)
        results.append(result)
    return {"statusCode": 200, "body": json.dumps(results)}


def process(bucket: str, key: str) -> dict:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported format: {ext}")

    timestamp  = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_stem  = re.sub(r"[^a-zA-Z0-9]", "-", key.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    job_name   = f"voxiq-{safe_stem}-{timestamp}"[:200]
    media_uri  = f"s3://{bucket}/{key}"
    output_key = f"transcripts/{job_name}.json"
    now        = datetime.now(timezone.utc).isoformat()

    # Extract org_id from key path (raw-audio/{org_id}/filename.mp3)
    parts  = key.split("/")
    org_id = parts[1] if len(parts) >= 3 else "default"

    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": media_uri},
        MediaFormat=ext,
        LanguageCode=LANGUAGE_CODE,
        OutputBucketName=RESULTS_BUCKET,
        OutputKey=output_key,
        Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
    )

    dynamodb.Table(TABLE).put_item(Item={
        "call_id":        job_name,
        "created_at":     now,
        "updated_at":     now,
        "org_id":         org_id,
        "status":         "TRANSCRIBING",
        "caller_phone":   "unknown",
        "audio_key":      key,
        "transcript_key": output_key,
        "source_bucket":  bucket,
        "language_code":  LANGUAGE_CODE,
        "vcon": {
            "vcon":    "0.0.1",
            "uuid":    job_name,
            "created": now,
            "parties": [],
            "dialog":  [],
            "analysis": [],
        },
    })

    print(f"Transcribe job started: {job_name}")
    return {"job_name": job_name, "status": "TRANSCRIBING"}
