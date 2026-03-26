"""
Aurora PostgreSQL helpers for the query-segments Lambda.

Performs a pgvector cosine similarity search over segment_embeddings,
joining back to segments to retrieve start/end timestamps.
"""

import os

import boto3

CLUSTER_ARN = os.environ["AURORA_CLUSTER_ARN"]
SECRET_ARN  = os.environ["AURORA_SECRET_ARN"]
DB_NAME     = os.environ.get("AURORA_DB_NAME", "lectureclip")

rds_data = boto3.client("rds-data")

# Cosine similarity: 1 - (embedding <=> query_vector).
# HNSW index on segment_embeddings uses vector_cosine_ops so this query is
# index-accelerated.  Results are filtered to a single lecture and limited
# to k rows.
_SEARCH_SQL = """
SELECT s.start_s,
       s.end_s,
       1 - (se.embedding <=> :vec::vector) AS similarity
FROM   segment_embeddings se
JOIN   segments s ON se.segment_id = s.segment_id
JOIN   lectures l ON s.lecture_id  = l.lecture_id
WHERE  l.video_uri = :video_uri
ORDER  BY similarity DESC
LIMIT  :k
"""


def search_segments(video_uri: str, embedding: list, k: int) -> list:
    """
    Return the top-k most similar segments for a video uri.

    Parameters
    ----------
    video_uri : str
        S3 URI of the video (e.g. "s3://bucket/key"). Matches lectures.video_uri.
    embedding : list[float]
        Query vector produced by bedrock_utils.embed_text().
    k : int
        Number of results to return.

    Returns
    -------
    list of {"start": float, "end": float} dicts, ordered by similarity.
    """
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"

    resp = rds_data.execute_statement(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DB_NAME,
        sql=_SEARCH_SQL,
        includeResultMetadata=True,
        parameters=[
            {"name": "vec",       "value": {"stringValue": vec_str}},
            {"name": "video_uri", "value": {"stringValue": video_uri}},
            {"name": "k",         "value": {"longValue": k}},
        ],
    )

    cols = [c["label"] for c in resp.get("columnMetadata", [])]
    rows = [
        dict(zip(cols, [list(field.values())[0] for field in row]))
        for row in resp.get("records", [])
    ]
    return [{"start": float(r["start_s"]), "end": float(r["end_s"])} for r in rows]