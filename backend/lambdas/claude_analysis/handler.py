"""
Lambda 3 — AI Analysis using AWS Comprehend (Free Tier)
--------------------------------------------------------
Fires when Transcribe writes its JSON output to the results bucket.
Uses AWS Comprehend (free) instead of Claude API for:
  - Sentiment analysis (positive / neutral / negative / mixed)
  - Key phrase extraction (topics)
  - Entity detection (names, places, organisations)

Built to be provider-agnostic — swapping in Claude is a one-function change.
"""
import json, os, urllib.parse
from datetime import datetime, timezone

import boto3

s3          = boto3.client("s3")
dynamodb    = boto3.resource("dynamodb")
comprehend  = boto3.client("comprehend")

TABLE          = os.environ["DYNAMODB_TABLE"]
RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]


# ------------------------------------------------------------------ #
# Entry point
# ------------------------------------------------------------------ #

def lambda_handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key    = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        print(f"Transcript ready: s3://{bucket}/{key}")
        process(bucket, key)
    return {"statusCode": 200}


# ------------------------------------------------------------------ #
# Core pipeline
# ------------------------------------------------------------------ #

def process(bucket: str, key: str):
    # 1. Read the Transcribe output JSON from S3
    obj             = s3.get_object(Bucket=bucket, Key=key)
    transcript_data = json.loads(obj["Body"].read())
    full_text       = transcript_data["results"]["transcripts"][0]["transcript"]
    job_name        = transcript_data["jobName"]

    if not full_text.strip():
        update_status(job_name, "FAILED", {"error": "Empty transcript"})
        return

    # 2. Build speaker-separated transcript if available
    speaker_text = build_speaker_transcript(transcript_data)

    # 3. Run AWS Comprehend analysis (free tier)
    analysis = analyse_with_comprehend(speaker_text or full_text)

    # 4. Update DynamoDB record to COMPLETE
    update_status(job_name, "COMPLETE", {
        "summary":          analysis["summary"],
        "sentiment":        analysis["sentiment"],
        "routing_category": analysis["routing_category"],
        "caller_intent":    analysis["caller_intent"],
        "key_topics":       analysis["key_topics"],
        "confidence_score": str(analysis["confidence"]),
        "full_transcript":  full_text,
        "vcon_analysis": [{
            "type":   "ai_analysis",
            "vendor": "aws_comprehend",
            "body":   analysis,
        }],
    })
    print(f"Analysis complete for: {job_name}")


# ------------------------------------------------------------------ #
# AWS Comprehend analysis
# ------------------------------------------------------------------ #

def analyse_with_comprehend(transcript: str) -> dict:
    """
    Runs three Comprehend API calls:
      1. detect_sentiment      — positive / neutral / negative / mixed
      2. detect_key_phrases    — extracts main topics from the text
      3. detect_entities       — finds names, places, organisations

    All three are FREE up to 50,000 units/month on AWS free tier.
    """

    # Comprehend has a 5000 byte limit per request — trim if needed
    text = transcript[:4500]

    # --- 1. Sentiment ---
    sentiment_resp  = comprehend.detect_sentiment(Text=text, LanguageCode="en")
    raw_sentiment   = sentiment_resp["Sentiment"].lower()          # POSITIVE → positive
    sentiment_score = sentiment_resp["SentimentScore"]
    confidence      = round(max(sentiment_score.values()), 2)

    # Normalise MIXED → neutral for simplicity
    sentiment = raw_sentiment if raw_sentiment in ("positive", "negative", "neutral") else "neutral"

    # --- 2. Key phrases (topics) ---
    phrases_resp = comprehend.detect_key_phrases(Text=text, LanguageCode="en")
    key_topics   = [
        p["Text"] for p in phrases_resp["KeyPhrases"]
        if p["Score"] > 0.85          # only high-confidence phrases
    ][:6]                             # cap at 6 topics

    # --- 3. Entities ---
    entities_resp = comprehend.detect_entities(Text=text, LanguageCode="en")
    entities      = [
        {"text": e["Text"], "type": e["Type"]}
        for e in entities_resp["Entities"]
        if e["Score"] > 0.85
    ]

    # --- 4. Derive routing category from key phrases ---
    routing_category = derive_routing_category(key_topics, transcript)

    # --- 5. Build a plain-English summary from the data ---
    summary       = build_summary(sentiment, key_topics, routing_category, transcript)
    caller_intent = build_caller_intent(key_topics, routing_category)

    return {
        "sentiment":        sentiment,
        "key_topics":       key_topics,
        "entities":         entities,
        "routing_category": routing_category,
        "summary":          summary,
        "caller_intent":    caller_intent,
        "confidence":       confidence,
        "provider":         "aws_comprehend",
        # Raw Comprehend scores stored for future model comparison
        "sentiment_scores": {
            "positive": round(sentiment_score["Positive"], 3),
            "negative": round(sentiment_score["Negative"], 3),
            "neutral":  round(sentiment_score["Neutral"],  3),
            "mixed":    round(sentiment_score["Mixed"],    3),
        },
    }


def derive_routing_category(topics: list, transcript: str) -> str:
    """
    Maps key phrases to a routing category using keyword matching.
    Provider-agnostic — works the same whether topics came from
    Comprehend or Claude.
    """
    text_lower = (transcript + " " + " ".join(topics)).lower()

    rules = [
        ("billing",           ["bill", "invoice", "charge", "payment", "refund", "overcharged", "credit"]),
        ("technical_support", ["not working", "broken", "error", "issue", "problem", "bug", "crash", "slow"]),
        ("sales",             ["price", "pricing", "buy", "purchase", "upgrade", "plan", "discount", "offer"]),
        ("complaints",        ["complaint", "unhappy", "frustrated", "angry", "terrible", "awful", "unacceptable"]),
        ("appointment",       ["appointment", "schedule", "book", "meeting", "available", "slot", "time"]),
        ("general_inquiry",   ["question", "information", "how do", "what is", "can you", "help"]),
    ]

    for category, keywords in rules:
        if any(kw in text_lower for kw in keywords):
            return category

    return "general_inquiry"


def build_summary(sentiment: str, topics: list, category: str, transcript: str) -> str:
    """
    Builds a readable one-sentence summary from Comprehend outputs.
    Not as rich as Claude — but free and still useful.
    """
    topic_str    = ", ".join(topics[:3]) if topics else "general matters"
    category_str = category.replace("_", " ")
    sentiment_str = {
        "positive": "The caller seemed satisfied",
        "negative": "The caller seemed frustrated",
        "neutral":  "The call was straightforward",
    }.get(sentiment, "The call covered")

    word_count = len(transcript.split())
    length_str = "brief" if word_count < 50 else "detailed" if word_count > 200 else "standard"

    return (
        f"{sentiment_str}. This was a {length_str} {category_str} call "
        f"covering: {topic_str}."
    )


def build_caller_intent(topics: list, category: str) -> str:
    """Derives a plain-English intent statement from the routing category."""
    intent_map = {
        "billing":           "The caller wanted help with a billing or payment issue.",
        "technical_support": "The caller needed technical assistance with a product or service.",
        "sales":             "The caller was enquiring about purchasing or upgrading.",
        "complaints":        "The caller wanted to raise a complaint or express dissatisfaction.",
        "appointment":       "The caller wanted to schedule or change an appointment.",
        "general_inquiry":   "The caller had a general question or needed information.",
    }
    return intent_map.get(category, "The caller's intent could not be determined.")


# ------------------------------------------------------------------ #
# Speaker transcript builder (unchanged from original)
# ------------------------------------------------------------------ #

def build_speaker_transcript(data: dict) -> str:
    """Formats transcript with Speaker 0 / Speaker 1 labels if available."""
    try:
        items   = data["results"]["items"]
        labels  = data["results"]["speaker_labels"]["segments"]
        mapping = {}
        for seg in labels:
            for item in seg["items"]:
                mapping[item["start_time"]] = seg["speaker_label"]

        lines, current_speaker, words = [], None, []
        for item in items:
            if item["type"] == "punctuation":
                if words:
                    words[-1] += item["alternatives"][0]["content"]
                continue
            spk  = mapping.get(item.get("start_time", ""), current_speaker)
            word = item["alternatives"][0]["content"]
            if spk != current_speaker:
                if words:
                    lines.append(f"{current_speaker}: {' '.join(words)}")
                current_speaker, words = spk, [word]
            else:
                words.append(word)
        if words:
            lines.append(f"{current_speaker}: {' '.join(words)}")
        return "\n".join(lines)
    except Exception:
        return ""


# ------------------------------------------------------------------ #
# DynamoDB updater (unchanged from original)
# ------------------------------------------------------------------ #

def update_status(job_name: str, status: str, extra: dict):
    """Updates the DynamoDB record for the completed job."""
    table = dynamodb.Table(TABLE)

    resp  = table.query(
        IndexName="StatusIndex",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("status").eq("TRANSCRIBING"),
    )
    items = [i for i in resp.get("Items", []) if i["call_id"] == job_name]

    if not items:
        scan  = table.scan(FilterExpression=boto3.dynamodb.conditions.Attr("call_id").eq(job_name))
        items = scan.get("Items", [])

    if not items:
        print(f"WARNING: No DynamoDB record found for {job_name}")
        return

    item         = items[0]
    now          = datetime.now(timezone.utc).isoformat()
    update_expr  = "SET #s = :s, updated_at = :u"
    names        = {"#s": "status"}
    values       = {":s": status, ":u": now}

    for i, (k, v) in enumerate(extra.items()):
        update_expr     += f", #{k} = :v{i}"
        names[f"#{k}"]   = k
        values[f":v{i}"] = v

    table.update_item(
        Key={"call_id": item["call_id"], "created_at": item["created_at"]},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )
