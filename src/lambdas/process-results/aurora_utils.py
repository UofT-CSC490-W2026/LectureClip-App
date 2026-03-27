"""
Aurora PostgreSQL helpers for the process-results Lambda.

Writes lecture metadata, transcript segments, and embedding vectors via the
RDS Data API — no direct database connection required.
"""

import json
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
    append_record = records.append
    execute = _execute
    namespace = uuid.NAMESPACE_URL
    make_segment_id = uuid.uuid5
    last_index = len(segments) - 1

    # TODO: batch the insert call
    for idx, (start_s, _speaker, text) in enumerate(segments):
        start_s_float = float(start_s)
        end_s = float(segments[idx + 1][0]) if idx < last_index else start_s_float + 30.0
        segment_id = str(make_segment_id(namespace, f"{lecture_id}:{idx}"))
        execute(
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
                {"name": "start_s", "value": {"doubleValue": start_s_float}},
                {"name": "end_s",   "value": {"doubleValue": end_s}},
                {"name": "text",    "value": {"stringValue": text}},
            ],
        )
        append_record((segment_id, start_s_float, end_s, text))
    return records


def insert_embeddings(segment_records, embeddings, model_id):
    # TODO: Batch the RDS execute call
    """
    Insert embedding vectors into segment_embeddings.

    segment_records: list of (segment_id, start_s, end_s, text) from insert_segments
    embeddings:      list of dicts with 'embedding' key from bedrock_utils
    model_id:        Bedrock model ID string stored alongside each vector
    """
    execute = _execute
    new_embedding_id = uuid.uuid4
    vector_to_str = json.dumps

    for (segment_id, *_), emb_record in zip(segment_records, embeddings):
        embedding_id = str(new_embedding_id())
        # json.dumps runs in C and already emits the pgvector-compatible list
        # syntax we need when separators remove whitespace.
        vector_str = vector_to_str(emb_record["embedding"], separators=(",", ":"))
        execute(
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