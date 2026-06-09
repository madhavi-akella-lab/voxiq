"""
Lambda 4 — Get Calls
API endpoint: GET /calls?org_id=default&limit=50
Returns call records from DynamoDB for the React dashboard.
"""
import json, os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
TABLE    = os.environ["DYNAMODB_TABLE"]


def lambda_handler(event, context):
    params   = event.get("queryStringParameters") or {}
    org_id   = params.get("org_id", "default")
    limit    = min(int(params.get("limit", "50")), 100)
    status   = params.get("status")          # optional filter
    phone    = params.get("caller_phone")    # optional filter

    table = dynamodb.Table(TABLE)

    if phone:
        items = query_by_phone(table, phone, limit)
    elif status:
        items = query_by_status(table, status, limit)
    else:
        items = query_by_org(table, org_id, limit)

    # Convert Decimal → float for JSON serialisation
    items = [_clean(i) for i in items]

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"calls": items, "count": len(items)}),
    }


def query_by_org(table, org_id: str, limit: int):
    return table.query(
        IndexName="OrgDateIndex",
        KeyConditionExpression=Key("org_id").eq(org_id),
        ScanIndexForward=False,
        Limit=limit,
    ).get("Items", [])


def query_by_status(table, status: str, limit: int):
    return table.query(
        IndexName="StatusIndex",
        KeyConditionExpression=Key("status").eq(status),
        ScanIndexForward=False,
        Limit=limit,
    ).get("Items", [])


def query_by_phone(table, phone: str, limit: int):
    return table.query(
        IndexName="PhoneIndex",
        KeyConditionExpression=Key("caller_phone").eq(phone),
        ScanIndexForward=False,
        Limit=limit,
    ).get("Items", [])


def _clean(item: dict) -> dict:
    """Recursively convert Decimal to float/int for JSON."""
    from decimal import Decimal
    if isinstance(item, dict):
        return {k: _clean(v) for k, v in item.items()}
    if isinstance(item, list):
        return [_clean(v) for v in item]
    if isinstance(item, Decimal):
        return float(item)
    return item
