"""
Lambda 2 — S3 Trigger → AssemblyAI Transcription (Free Tier)
--------------------------------------------------------------
Fires automatically when an audio file lands in the raw-audio/ prefix.
Uses AssemblyAI (free, 100 hours/month) instead of AWS Transcribe.
Writes a TRANSCRIBING record to DynamoDB immediately.
AssemblyAI calls back via webhook when transcription is complete,
which triggers the claude_analysis Lambda.
"""
import json, os, re, urllib.parse, urllib.request
from datetime import datetime, timezone

import boto3

dynamodb = boto3.resource("dynamodb")
ssm      = boto3.client("ssm")
s3       = boto3.client("s3")

TABLE          = os.environ["DYNAMODB_TABLE"]
RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]

SUPPORTED = {"mp3", "mp4", "wav", "flac", "ogg", "m4a", "webm"}

_assemblyai_key = None

def get_api_key() -> str:
    global _assemblyai_key
    if _assemblyai_key:
        return _assemblyai_key
    resp = ssm.get_parameter(Name="/voxiq/assemblyai_api_key", WithDecryption=True)
    _assemblyai_key = resp["Parameter"]["Value"]
    return _assemblyai_key


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

    # Generate a presigned URL so AssemblyAI can download the audio from S3
    audio_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600,  # 1 hour
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_stem = re.sub(r"[^a-zA-Z0-9]", "-", key.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    job_name  = f"voxiq-{safe_stem}-{timestamp}"[:200]
    now       = datetime.now(timezone.utc).isoformat()

    parts  = key.split("/")
    org_id = parts[1] if len(parts) >= 3 else "default"

    # Submit to AssemblyAI
    transcript_id = submit_to_assemblyai(audio_url, job_name)
    print(f"AssemblyAI job submitted: {transcript_id}")

    # Save to DynamoDB
    dynamodb.Table(TABLE).put_item(Item={
        "call_id":          job_name,
        "created_at":       now,
        "updated_at":       now,
        "org_id":           org_id,
        "status":           "TRANSCRIBING",
        "caller_phone":     "unknown",
        "audio_key":        key,
        "transcript_key":   transcript_id,
        "source_bucket":    bucket,
        "language_code":    "en-US",
        "assemblyai_id":    transcript_id,
        "vcon": {
            "vcon":    "0.0.1",
            "uuid":    job_name,
            "created": now,
            "parties": [],
            "dialog":  [],
            "analysis": [],
        },
    })

    # Poll AssemblyAI for result and process inline
    # (simpler than webhook for demo purposes)
    transcript_text = poll_assemblyai(transcript_id)

    if transcript_text:
        # Save transcript to results bucket
        result_key = f"transcripts/{job_name}.json"
        transcript_data = {
            "jobName": job_name,
            "results": {
                "transcripts": [{"transcript": transcript_text}],
                "items": []
            }
        }
        s3.put_object(
            Bucket=RESULTS_BUCKET,
            Key=result_key,
            Body=json.dumps(transcript_data),
            ContentType="application/json"
        )
        print(f"Transcript saved to s3://{RESULTS_BUCKET}/{result_key}")

    return {"job_name": job_name, "assemblyai_id": transcript_id, "status": "TRANSCRIBING"}


def submit_to_assemblyai(audio_url: str, job_name: str) -> str:
    """Submit audio to AssemblyAI and return the transcript ID."""
    api_key = get_api_key()

    body = json.dumps({
        "audio_url":       audio_url,
        "speaker_labels":  True,
        "language_code":   "en",
    }).encode()

    req = urllib.request.Request(
        "https://api.assemblyai.com/v2/transcript",
        data=body,
        headers={
            "Authorization": api_key,
            "Content-Type":  "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    return data["id"]


def poll_assemblyai(transcript_id: str, max_attempts: int = 60) -> str:
    """Poll AssemblyAI until transcription is complete. Returns transcript text."""
    import time
    api_key = get_api_key()

    for attempt in range(max_attempts):
        req = urllib.request.Request(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers={"Authorization": api_key},
            method="GET",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        status = data.get("status")
        print(f"AssemblyAI status: {status} (attempt {attempt + 1})")

        if status == "completed":
            return data.get("text", "")
        elif status == "error":
            print(f"AssemblyAI error: {data.get('error')}")
            return ""

        time.sleep(3)  # wait 3 seconds between polls

    print("AssemblyAI polling timed out")
    return ""
