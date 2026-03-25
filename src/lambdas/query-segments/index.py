import json
import os

from bedrock_utils import embed_text
from aurora_utils import search_segments

EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBEDDING_DIM      = int(os.environ.get("EMBEDDING_DIM", "1024"))
BUCKET_NAME        = os.environ.get("BUCKET_NAME")

if not BUCKET_NAME or not BUCKET_NAME.strip():
    raise RuntimeError("BUCKET_NAME environment variable is required for query-segments Lambda")
def handler(event, context):
    """
    Semantic search over lecture transcript segments.

    Expected request body (JSON):
        videoId  — videoID name (returned by the upload endpoint)
        query    — natural language query string
        k        — optional, number of results (default 5)

    Returns:
        { "segments": [{ "start": <float>, "end": <float> }, ...] }

    Segments are ordered by cosine similarity (most relevant first).
    """
    print("Event:", json.dumps(event))

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _resp(400, {"error": "Request body must be valid JSON"})

    video_id = body.get("videoId")
    query    = body.get("query")

    raw_k = body.get("k", 5)
    try:
        k = int(raw_k)
    except (TypeError, ValueError):
        return _resp(400, {"error": "k must be an integer"})

    # Enforce reasonable bounds for k to protect the DB query.
    if k < 1 or k > 100:
        return _resp(400, {"error": "k must be between 1 and 100"})
    if not video_id:
        return _resp(400, {"error": "videoId is required"})
    if not query:
        return _resp(400, {"error": "query is required"})

    # videoId is the S3 object key returned by the upload endpoint.
    # Reconstruct the full S3 URI to match lectures.video_uri in the DB.
    video_uri = f"s3://{BUCKET_NAME}/{video_id}"

    vector   = embed_text(query, EMBEDDING_MODEL_ID, EMBEDDING_DIM)
    segments = search_segments(video_uri, vector, k)

    print(f"Returning {len(segments)} segments for {video_uri!r}")
    return _resp(200, {"segments": segments})


def _resp(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }