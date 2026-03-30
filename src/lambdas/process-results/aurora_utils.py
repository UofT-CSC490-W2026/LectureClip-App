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


def _batch_execute(sql, parameter_sets):
    """Run one SQL statement against multiple parameter sets in a single RDS Data API call."""
    return rds_data.batch_execute_statement(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DB_NAME,
        sql=sql,
        parameterSets=parameter_sets,
    )


def upsert_lecture(video_uri, user_id=None):
    """
    Insert a lecture row keyed by a deterministic UUID derived from video_uri.
    Sets user_id when provided. Does nothing on conflict — safe to call on
    repeated processing of the same video.
    Returns the lecture_id string.
    """
    lecture_id = str(uuid.uuid5(uuid.NAMESPACE_URL, video_uri))
    title = video_uri.rsplit("/", 1)[-1]
    params = [
        {"name": "lecture_id", "value": {"stringValue": lecture_id}},
        {"name": "title",      "value": {"stringValue": title}},
        {"name": "video_uri",  "value": {"stringValue": video_uri}},
        {"name": "user_id",    "value": {"stringValue": user_id} if user_id else {"isNull": True}},
    ]
    _execute(
        """
        INSERT INTO lectures (lecture_id, title, video_uri, user_id)
        VALUES (:lecture_id::uuid, :title, :video_uri, :user_id::uuid)
        ON CONFLICT (lecture_id) DO UPDATE
            SET user_id = COALESCE(EXCLUDED.user_id, lectures.user_id)
        """,
        params,
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
    namespace = uuid.NAMESPACE_URL
    last_index = len(segments) - 1
    records = []
    parameter_sets = []

    for idx, (start_s, _speaker, text) in enumerate(segments):
        start_s_float = float(start_s)
        end_s = float(segments[idx + 1][0]) if idx < last_index else start_s_float + 30.0
        segment_id = str(uuid.uuid5(namespace, f"{lecture_id}:{idx}"))
        records.append((segment_id, start_s_float, end_s, text))
        parameter_sets.append([
            {"name": "sid",     "value": {"stringValue": segment_id}},
            {"name": "lid",     "value": {"stringValue": lecture_id}},
            {"name": "idx",     "value": {"longValue":   idx}},
            {"name": "start_s", "value": {"doubleValue": start_s_float}},
            {"name": "end_s",   "value": {"doubleValue": end_s}},
            {"name": "text",    "value": {"stringValue": text}},
        ])

    if parameter_sets:
        _batch_execute(
            """
            INSERT INTO segments (segment_id, lecture_id, idx, start_s, end_s, text)
            VALUES (:sid::uuid, :lid::uuid, :idx, :start_s, :end_s, :text)
            ON CONFLICT (lecture_id, idx) DO UPDATE
                SET start_s = EXCLUDED.start_s,
                    end_s   = EXCLUDED.end_s,
                    text    = EXCLUDED.text
            """,
            parameter_sets,
        )
    return records


def insert_embeddings(segment_records, embeddings, model_id):
    """
    Insert embedding vectors into segment_embeddings.

    segment_records: list of (segment_id, start_s, end_s, text) from insert_segments
    embeddings:      list of dicts with 'embedding' key from bedrock_utils
    model_id:        Bedrock model ID string stored alongside each vector
    """
    parameter_sets = []
    for (segment_id, *_), emb_record in zip(segment_records, embeddings):
        embedding_id = str(uuid.uuid4())
        # json.dumps runs in C and already emits the pgvector-compatible list
        # syntax we need when separators remove whitespace.
        vector_str = json.dumps(emb_record["embedding"], separators=(",", ":"))
        parameter_sets.append([
            {"name": "eid",               "value": {"stringValue": embedding_id}},
            {"name": "sid",               "value": {"stringValue": segment_id}},
            {"name": "vec",               "value": {"stringValue": vector_str}},
            {"name": "model_id",          "value": {"stringValue": model_id}},
            {"name": "is_frame_embedding", "value": {"booleanValue": False}},
        ])

    if parameter_sets:
        _batch_execute(
            """
            INSERT INTO segment_embeddings (embedding_id, segment_id, embedding, model_id, is_frame_embedding)
            VALUES (:eid::uuid, :sid::uuid, :vec::vector, :model_id, :is_frame_embedding)
            ON CONFLICT DO NOTHING
            """,
            parameter_sets,
        )


def insert_frame_embeddings(segment_records, frame_emb_data, model_id):
    """
    Insert pre-computed image embedding vectors produced by the segment-frame
    container into segment_embeddings.

    Each frame embedding is linked to the same segment row as the paired text
    embedding — identified by position index (idx) — so callers can retrieve
    both modalities for a segment via a single segment_id lookup.

    segment_records: list of (segment_id, start_s, end_s, text) from insert_segments
    frame_emb_data:  list of {idx, start_s, end_s, speaker, embedding} from S3 JSON
    model_id:        Bedrock image model ID (e.g. 'amazon.titan-embed-image-v1')
    """
    idx_to_segment_id = {i: rec[0] for i, rec in enumerate(segment_records)}

    parameter_sets = []
    for entry in frame_emb_data:
        segment_id = idx_to_segment_id.get(entry.get("idx"))
        if segment_id is None:
            continue
        embedding_id = str(uuid.uuid4())
        vector_str = json.dumps(entry["embedding"], separators=(",", ":"))
        parameter_sets.append([
            {"name": "eid",               "value": {"stringValue": embedding_id}},
            {"name": "sid",               "value": {"stringValue": segment_id}},
            {"name": "vec",               "value": {"stringValue": vector_str}},
            {"name": "model_id",          "value": {"stringValue": model_id}},
            {"name": "is_frame_embedding", "value": {"booleanValue": True}},
        ])

    if parameter_sets:
        _batch_execute(
            """
            INSERT INTO segment_embeddings (embedding_id, segment_id, embedding, model_id, is_frame_embedding)
            VALUES (:eid::uuid, :sid::uuid, :vec::vector, :model_id, :is_frame_embedding)
            ON CONFLICT DO NOTHING
            """,
            parameter_sets,
        )