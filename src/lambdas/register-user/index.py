"""
Upserts a user row keyed by a deterministic UUID derived from their email.
Called by the frontend on every sign-in so the users table stays in sync
with Cognito without requiring any additional identity lookup.

The user_id is computed as uuid5(NAMESPACE_URL, "mailto:{email}"), matching
the same generation used by process-results when it sets lectures.user_id.
"""

import json
import os
import uuid

import boto3

CLUSTER_ARN = os.environ["AURORA_CLUSTER_ARN"]
SECRET_ARN  = os.environ["AURORA_SECRET_ARN"]
DB_NAME     = os.environ.get("AURORA_DB_NAME", "lectureclip")

rds_data = boto3.client("rds-data")

_CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

_UPSERT_SQL = """
INSERT INTO users (user_id, email, display_name)
VALUES (:user_id::uuid, :email, :display_name)
ON CONFLICT (email) DO UPDATE
    SET display_name = COALESCE(EXCLUDED.display_name, users.display_name)
"""


def user_id_for(email: str) -> str:
    """Deterministic UUID5 from email — must match process-results derivation."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"mailto:{email}"))


def handler(event, context):
    http_method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "")
    )
    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": _CORS_HEADERS, "body": ""}

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _resp(400, {"error": "Request body must be valid JSON"})

    email = (body.get("email") or "").strip().lower()
    if not email:
        return _resp(400, {"error": "email is required"})

    display_name = (body.get("displayName") or "").strip() or None
    uid = user_id_for(email)

    try:
        rds_data.execute_statement(
            resourceArn=CLUSTER_ARN,
            secretArn=SECRET_ARN,
            database=DB_NAME,
            sql=_UPSERT_SQL,
            parameters=[
                {"name": "user_id",      "value": {"stringValue": uid}},
                {"name": "email",        "value": {"stringValue": email}},
                {"name": "display_name", "value": {"stringValue": display_name} if display_name
                                                  else {"isNull": True}},
            ],
        )
    except Exception as e:
        print(f"Aurora upsert failed: {e}")
        return _resp(500, {"error": "Failed to register user"})

    return _resp(200, {"userId": uid, "email": email})


def _resp(status_code, body):
    return {
        "statusCode": status_code,
        "headers":    {"Content-Type": "application/json", **_CORS_HEADERS},
        "body":       json.dumps(body),
    }
