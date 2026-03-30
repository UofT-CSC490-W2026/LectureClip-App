"""
LectureClip Aurora PostgreSQL schema migration Lambda.

Executed once after each deployment by CI (scripts/deploy.sh).
All DDL statements use IF NOT EXISTS — safe to re-run idempotently.

Environment variables (injected by Terraform):
    AURORA_CLUSTER_ARN  — RDS cluster ARN for Data API calls
    AURORA_SECRET_ARN   — Secrets Manager ARN for master credentials
    AURORA_DB_NAME      — Database name (default: lectureclip)
"""

import json
import os

import boto3

CLUSTER_ARN = os.environ["AURORA_CLUSTER_ARN"]
SECRET_ARN  = os.environ["AURORA_SECRET_ARN"]
DB_NAME     = os.environ.get("AURORA_DB_NAME", "lectureclip")

rds_data = boto3.client("rds-data")

# ---------------------------------------------------------------------------
# DDL — executed in order, each auto-committed by the Data API.
# The vector extension must be created before any vector column.
# ---------------------------------------------------------------------------

DDL_STATEMENTS = [
    # 0. pgvector extension
    "CREATE EXTENSION IF NOT EXISTS vector",

    # 1. Lecture metadata
    """
    CREATE TABLE IF NOT EXISTS lectures (
        lecture_id   UUID        PRIMARY KEY,
        course_id    TEXT,
        title        TEXT,
        duration_s   REAL,
        video_uri    TEXT        NOT NULL,
        ingested_ts  TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    # 2. Timestamped transcript segments
    """
    CREATE TABLE IF NOT EXISTS segments (
        segment_id  UUID  PRIMARY KEY,
        lecture_id  UUID  NOT NULL REFERENCES lectures(lecture_id),
        idx         INT   NOT NULL,
        start_s     REAL  NOT NULL,
        end_s       REAL  NOT NULL,
        text        TEXT  NOT NULL,
        UNIQUE (lecture_id, idx)
    )
    """,

    # 3. Fixed evaluation queries
    """
    CREATE TABLE IF NOT EXISTS eval_queries (
        query_id    UUID PRIMARY KEY,
        lecture_id  UUID NOT NULL REFERENCES lectures(lecture_id),
        query_text  TEXT NOT NULL
    )
    """,

    # 4. Ground-truth relevant spans per query
    """
    CREATE TABLE IF NOT EXISTS truth_spans (
        span_id    UUID     PRIMARY KEY,
        query_id   UUID     NOT NULL REFERENCES eval_queries(query_id),
        start_s    REAL     NOT NULL,
        end_s      REAL     NOT NULL,
        relevance  SMALLINT NOT NULL
    )
    """,

    # 5. Task efficiency outcomes
    """
    CREATE TABLE IF NOT EXISTS eval_task_runs (
        run_id                   UUID PRIMARY KEY,
        query_id                 UUID NOT NULL REFERENCES eval_queries(query_id),
        condition                TEXT NOT NULL,
        participant_id           TEXT,
        time_to_first_relevant_s REAL,
        time_to_understanding_s  REAL,
        interaction_count        INT,
        interaction_log_uri      TEXT
    )
    """,

    # 6. Sub-lecture quality judgments
    """
    CREATE TABLE IF NOT EXISTS sublecture_ratings (
        rating_id  UUID     PRIMARY KEY,
        query_id   UUID     NOT NULL REFERENCES eval_queries(query_id),
        condition  TEXT     NOT NULL,
        rater_id   TEXT,
        relevance  SMALLINT NOT NULL,
        coverage   SMALLINT NOT NULL,
        coherence  SMALLINT NOT NULL,
        redundancy SMALLINT NOT NULL,
        preferred  BOOLEAN,
        notes      TEXT
    )
    """,

    # 7. Segment embeddings — pgvector table for similarity search
    """
    CREATE TABLE IF NOT EXISTS segment_embeddings (
        embedding_id      UUID         PRIMARY KEY,
        segment_id        UUID         NOT NULL REFERENCES segments(segment_id),
        embedding         vector(1024) NOT NULL,
        model_id          TEXT         NOT NULL DEFAULT 'amazon.titan-embed-text-v2:0',
        is_frame_embedding BOOLEAN     NOT NULL DEFAULT false,
        created_ts        TIMESTAMPTZ  NOT NULL DEFAULT now()
    )
    """,

    # HNSW index for fast cosine similarity search
    """
    CREATE INDEX IF NOT EXISTS segment_embeddings_hnsw_idx
        ON segment_embeddings
        USING hnsw (embedding vector_cosine_ops)
    """,

    # 8. Backfill is_frame_embedding for tables created before this column existed
    """
    ALTER TABLE segment_embeddings
        ADD COLUMN IF NOT EXISTS is_frame_embedding BOOLEAN NOT NULL DEFAULT false
    """,

    # 9. Users — registered Cognito accounts
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id      UUID        PRIMARY KEY,
        email        TEXT        NOT NULL,
        display_name TEXT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT users_email_unique UNIQUE (email)
    )
    """,

    # 10. Associate lectures with users
    """
    ALTER TABLE lectures
        ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(user_id)
    """,

    # 11. Index for fast per-user lecture listing
    """
    CREATE INDEX IF NOT EXISTS lectures_user_id_idx
        ON lectures (user_id)
    """,

    # 12. Backfill user_id on lectures where the email segment of the S3 URI
    #     already matches a registered user.
    #     S3 URI format: s3://{bucket}/{timestamp}/{email}/{filename}
    #     split_part(uri, '/', 5) extracts the email component.
    """
    UPDATE lectures
    SET    user_id = u.user_id
    FROM   users u
    WHERE  lectures.user_id IS NULL
      AND  split_part(lectures.video_uri, '/', 5) = u.email
    """,
]


def _execute(sql):
    rds_data.execute_statement(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DB_NAME,
        sql=sql.strip(),
    )


def handler(event, context):
    print(f"Running {len(DDL_STATEMENTS)} DDL statement(s) on '{DB_NAME}'")

    for i, stmt in enumerate(DDL_STATEMENTS):
        preview = stmt.strip().splitlines()[0][:72]
        print(f"  [{i + 1}/{len(DDL_STATEMENTS)}] {preview}")
        _execute(stmt)

    print("Migration complete.")
    return {"statusCode": 200, "statementsExecuted": len(DDL_STATEMENTS)}