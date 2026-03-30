"""
Returns all lectures belonging to a user, ordered by most recent first.
Each result includes a short-lived presigned URL for client-side playback.

user_id is derived as uuid5(NAMESPACE_URL, "mailto:{email}") — identical to
the generation in register-user and process-results so all three agree without
any explicit ID exchange.
"""

import json
import os
import uuid

import boto3

CLUSTER_ARN = os.environ["AURORA_CLUSTER_ARN"]
SECRET_ARN  = os.environ["AURORA_SECRET_ARN"]
DB_NAME     = os.environ.get("AURORA_DB_NAME", "lectureclip")
BUCKET_NAME = os.environ["BUCKET_NAME"]
REGION      = os.environ.get("REGION", "ca-central-1")

PLAYBACK_URL_EXPIRY = 3600  # 1 hour

rds_data  = boto3.client("rds-data")
s3_client = boto3.client("s3", region_name=REGION)

_CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

_LIST_SQL = """
SELECT l.lecture_id::text,
       l.title,
       l.video_uri,
       l.ingested_ts AT TIME ZONE 'UTC' AS ingested_ts
FROM   lectures l
WHERE  l.user_id = :user_id::uuid
ORDER  BY l.ingested_ts DESC
"""


def user_id_for(email: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"mailto:{email}"))


def handler(event, context):
    http_method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "")
    )
    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": _CORS_HEADERS, "body": ""}

    params = event.get("queryStringParameters") or {}
    email = (params.get("userId") or "").strip().lower()
    if not email:
        return _resp(400, {"error": "userId query parameter is required"})

    uid = user_id_for(email)

    try:
        resp = rds_data.execute_statement(
            resourceArn=CLUSTER_ARN,
            secretArn=SECRET_ARN,
            database=DB_NAME,
            sql=_LIST_SQL,
            includeResultMetadata=True,
            parameters=[
                {"name": "user_id", "value": {"stringValue": uid}},
            ],
        )
    except Exception as e:
        print(f"Aurora query failed: {e}")
        return _resp(500, {"error": "Failed to query lectures"})

    cols = [c["label"] for c in resp.get("columnMetadata", [])]
    rows = [
        dict(zip(cols, [list(field.values())[0] for field in row]))
        for row in resp.get("records", [])
    ]

    lectures = []
    for row in rows:
        video_uri = row["video_uri"]
        prefix = f"s3://{BUCKET_NAME}/"
        s3_key = video_uri[len(prefix):] if video_uri.startswith(prefix) else video_uri

        try:
            playback_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": BUCKET_NAME, "Key": s3_key},
                ExpiresIn=PLAYBACK_URL_EXPIRY,
            )
        except Exception as e:
            print(f"Failed to generate presigned URL for {s3_key}: {e}")
            playback_url = None

        lectures.append({
            "lectureId":   row["lecture_id"],
            "videoId":     s3_key,
            "title":       row["title"],
            "ingestedAt":  str(row["ingested_ts"]),
            "playbackUrl": playback_url,
        })

    return _resp(200, {"lectures": lectures})


def _resp(status_code, body):
    return {
        "statusCode": status_code,
        "headers":    {"Content-Type": "application/json", **_CORS_HEADERS},
        "body":       json.dumps(body),
    }
