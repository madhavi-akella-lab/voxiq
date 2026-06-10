"""
Lambda 3 — AI Analysis using built-in keyword analysis
-------------------------------------------------------
No external AI services needed — works on any AWS account.
Uses keyword matching for sentiment, routing, and topic extraction.
Fast, free, and zero dependencies beyond the Python standard library.
"""
import json, os, urllib.parse, re
from datetime import datetime, timezone

import boto3

s3       = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

TABLE          = os.environ["DYNAMODB_TABLE"]
RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]


def lambda_handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key    = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        print(f"Transcript ready: s3://{bucket}/{key}")
        process(bucket, key)
    return {"statusCode": 200}


def process(bucket: str, key: str):
    # 1. Read transcript from S3
    obj             = s3.get_object(Bucket=bucket, Key=key)
    transcript_data = json.loads(obj["Body"].read())
    full_text       = transcript_data["results"]["transcripts"][0]["transcript"]
    job_name        = transcript_data["jobName"]

    if not full_text.strip():
        update_status(job_name, "FAILED", {"error": "Empty transcript"})
        return

    # 2. Analyse using built-in keyword engine
    analysis = analyse_text(full_text)

    # 3. Update DynamoDB
    update_status(job_name, "COMPLETE", {
        "summary":          analysis["summary"],
        "sentiment":        analysis["sentiment"],
        "routing_category": analysis["routing_category"],
        "caller_intent":    analysis["caller_intent"],
        "key_topics":       analysis["key_topics"],
        "confidence_score": str(analysis["confidence"]),
        "full_transcript":  full_text,
        "vcon_analysis": [{
            "type":   "keyword_analysis",
            "vendor": "built_in",
            "body":   analysis,
        }],
    })
    print(f"Analysis complete for: {job_name}")


def analyse_text(text: str) -> dict:
    """
    Analyses transcript text using keyword matching.
    No external services — works on any AWS account for free.
    """
    text_lower = text.lower()
    words      = re.findall(r'\b\w+\b', text_lower)
    word_set   = set(words)

    # --- Sentiment ---
    positive_words = {"thank", "thanks", "great", "good", "excellent", "happy",
                      "pleased", "wonderful", "amazing", "helpful", "appreciate",
                      "perfect", "love", "fantastic", "resolved", "fixed", "works"}
    negative_words = {"frustrated", "angry", "upset", "terrible", "awful", "bad",
                      "wrong", "broken", "doesn't work", "not working", "problem",
                      "issue", "complaint", "unhappy", "disappointed", "horrible",
                      "unacceptable", "charged", "overcharged", "refund", "cancel"}
    neutral_words  = {"question", "information", "help", "know", "understand",
                      "check", "verify", "confirm", "update", "status"}

    pos_score = len(word_set & positive_words)
    neg_score = len(word_set & negative_words)
    neu_score = len(word_set & neutral_words)

    if neg_score > pos_score:
        sentiment   = "negative"
        confidence  = round(min(0.95, 0.6 + neg_score * 0.05), 2)
    elif pos_score > neg_score:
        sentiment   = "positive"
        confidence  = round(min(0.95, 0.6 + pos_score * 0.05), 2)
    else:
        sentiment   = "neutral"
        confidence  = round(min(0.95, 0.6 + neu_score * 0.05), 2)

    # --- Routing category ---
    routing_rules = [
        ("billing",           ["bill", "invoice", "charge", "payment", "refund",
                                "overcharged", "credit", "cost", "price", "paid"]),
        ("technical_support", ["not working", "broken", "error", "issue", "problem",
                                "bug", "crash", "slow", "fix", "repair", "technical"]),
        ("sales",             ["buy", "purchase", "upgrade", "plan", "discount",
                                "offer", "pricing", "subscription", "trial"]),
        ("complaints",        ["complaint", "unhappy", "frustrated", "angry",
                                "terrible", "awful", "unacceptable", "manager"]),
        ("appointment",       ["appointment", "schedule", "book", "meeting",
                                "available", "slot", "time", "visit"]),
        ("general_inquiry",   ["question", "information", "how", "what", "when",
                                "where", "help", "understand", "know"]),
    ]

    routing_category = "general_inquiry"
    for category, keywords in routing_rules:
        if any(kw in text_lower for kw in keywords):
            routing_category = category
            break

    # --- Key topics (most frequent meaningful words) ---
    stop_words = {"the", "a", "an", "is", "it", "in", "on", "at", "to", "for",
                  "of", "and", "or", "but", "i", "you", "we", "my", "your",
                  "this", "that", "was", "are", "be", "have", "had", "with",
                  "can", "will", "just", "do", "did", "so", "if", "about"}

    word_freq = {}
    for word in words:
        if word not in stop_words and len(word) > 3:
            word_freq[word] = word_freq.get(word, 0) + 1

    key_topics = sorted(word_freq, key=word_freq.get, reverse=True)[:6]

    # --- Build summary ---
    word_count  = len(text.split())
    length_str  = "brief" if word_count < 50 else "detailed" if word_count > 200 else "standard"
    category_str = routing_category.replace("_", " ")
    sentiment_str = {
        "positive": "The caller seemed satisfied",
        "negative": "The caller seemed frustrated",
        "neutral":  "The call was straightforward",
    }.get(sentiment, "The call covered")

    topic_str = ", ".join(key_topics[:3]) if key_topics else "general matters"
    summary   = (f"{sentiment_str}. This was a {length_str} {category_str} call "
                 f"covering: {topic_str}.")

    # --- Caller intent ---
    intent_map = {
        "billing":           "The caller wanted help with a billing or payment issue.",
        "technical_support": "The caller needed technical assistance.",
        "sales":             "The caller was enquiring about purchasing or upgrading.",
        "complaints":        "The caller wanted to raise a complaint.",
        "appointment":       "The caller wanted to schedule or change an appointment.",
        "general_inquiry":   "The caller had a general question or needed information.",
    }

    return {
        "sentiment":        sentiment,
        "key_topics":       key_topics,
        "routing_category": routing_category,
        "summary":          summary,
        "caller_intent":    intent_map.get(routing_category, "General enquiry."),
        "confidence":       confidence,
        "provider":         "built_in_keyword_engine",
        "word_count":       word_count,
    }


def update_status(job_name: str, status: str, extra: dict):
    """Updates the DynamoDB record for the completed job."""
    table = dynamodb.Table(TABLE)

    resp  = table.query(
        IndexName="StatusIndex",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("status").eq("TRANSCRIBING"),
    )
    items = [i for i in resp.get("Items", []) if i["call_id"] == job_name]

    if not items:
        scan  = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr("call_id").eq(job_name)
        )
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
