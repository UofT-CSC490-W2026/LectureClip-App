"""
Aurora PostgreSQL helpers for the process-results Lambda.

Writes lecture metadata, transcript segments, and embedding vectors via the
RDS Data API — no direct database connection required.
"""

import os
import uuid

import boto3

CLUSTER_ARN = os.environ["AURORA_CLUSTER_ARN"]
SECRET_ARN  = os.environ["AURORA_SECRET_ARN"]
DB_NAME     = os.environ.get("AURORA_DB_NAME", "lectureclip")

rds_data = boto3.client("rds-data")


def _execute(sql, params=None):
    kwargs = {
        "resourceArn": CLUSTER_ARN,
        "secretArn":   SECRET_ARN,
        "database":    DB_NAME,
        "sql":         sql,
    }
    if params:
        kwargs["parameters"] = params
    return rds_data.execute_statement(**kwargs)


def upsert_lecture(video_uri):
    """
    Insert a lecture row keyed by a deterministic UUID derived from video_uri.
    Does nothing on conflict — safe to call on repeated processing of the same video.
    Returns the lecture_id string.
    """
    lecture_id = str(uuid.uuid5(uuid.NAMESPACE_URL, video_uri))
    title = video_uri.rsplit("/", 1)[-1]
    _execute(
        """
        INSERT INTO lectures (lecture_id, title, video_uri)
        VALUES (:lecture_id::uuid, :title, :video_uri)
        ON CONFLICT (lecture_id) DO NOTHING
        """,
        [
            {"name": "lecture_id", "value": {"stringValue": lecture_id}},
            {"name": "title",      "value": {"stringValue": title}},
            {"name": "video_uri",  "value": {"stringValue": video_uri}},
        ],
    )
    return lecture_id


def insert_segments(lecture_id, segments):
    """
    Upsert transcript segments into the DB.

    segments: list of (start_second, speaker_label, text) from transcript_utils

    Returns: list of (segment_id, start_s, end_s, text) for use by insert_embeddings.
    end_s for each segment is estimated as the start_s of the next segment (or +30 s
    for the last one).
    """
    records = []
    for idx, (start_s, _speaker, text) in enumerate(segments):
        end_s = float(segments[idx + 1][0]) if idx + 1 < len(segments) else float(start_s) + 30.0
        segment_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{lecture_id}:{idx}"))
        _execute(
            """
            INSERT INTO segments (segment_id, lecture_id, idx, start_s, end_s, text)
            VALUES (:sid::uuid, :lid::uuid, :idx, :start_s, :end_s, :text)
            ON CONFLICT (lecture_id, idx) DO UPDATE
                SET start_s = EXCLUDED.start_s,
                    end_s   = EXCLUDED.end_s,
                    text    = EXCLUDED.text
            """,
            [
                {"name": "sid",     "value": {"stringValue": segment_id}},
                {"name": "lid",     "value": {"stringValue": lecture_id}},
                {"name": "idx",     "value": {"longValue":   idx}},
                {"name": "start_s", "value": {"doubleValue": float(start_s)}},
                {"name": "end_s",   "value": {"doubleValue": end_s}},
                {"name": "text",    "value": {"stringValue": text}},
            ],
        )
        records.append((segment_id, float(start_s), end_s, text))
    return records


def insert_embeddings(segment_records, embeddings, model_id):
    """
    Insert embedding vectors into segment_embeddings.

    segment_records: list of (segment_id, start_s, end_s, text) from insert_segments
    embeddings:      list of dicts with 'embedding' key from bedrock_utils
    model_id:        Bedrock model ID string stored alongside each vector
    """
    for (segment_id, *_), emb_record in zip(segment_records, embeddings):
        embedding_id = str(uuid.uuid4())
        vector_str = "[" + ",".join(str(v) for v in emb_record["embedding"]) + "]"
        _execute(
            """
            INSERT INTO segment_embeddings (embedding_id, segment_id, embedding, model_id)
            VALUES (:eid::uuid, :sid::uuid, :vec::vector, :model_id)
            ON CONFLICT DO NOTHING
            """,
            [
                {"name": "eid",      "value": {"stringValue": embedding_id}},
                {"name": "sid",      "value": {"stringValue": segment_id}},
                {"name": "vec",      "value": {"stringValue": vector_str}},
                {"name": "model_id", "value": {"stringValue": model_id}},
            ],
        )