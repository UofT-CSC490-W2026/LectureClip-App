import json
import os
import uuid

import boto3

from constants import Model
from transcript_utils import fetch_and_parse_transcript
from bedrock_utils import generate_text_embeddings
from aurora_utils import upsert_lecture, insert_segments, insert_embeddings, insert_frame_embeddings

EMBEDDING_MODEL_ID       = os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-image-v1")
EMBEDDING_DIM            = int(os.environ.get("EMBEDDING_DIM", "1024"))
FRAME_EMBEDDING_MODEL_ID = os.environ.get("FRAME_EMBEDDING_MODEL_ID", "amazon.titan-embed-image-v1")

_s3 = boto3.client("s3")


def handler(event, context):
    """
    Generate text embeddings from an Amazon Transcribe transcript and persist
    them to Aurora PostgreSQL via the RDS Data API.

    Expected event keys (provided by Step Functions after process-transcribe
    signals task success):
        transcriptUrl  — HTTPS URL of the Transcribe JSON output on S3
        mediaUrl       — S3 URI of the source video (used as the lecture video_uri)
    """
    print("Event:", json.dumps(event))

    media_uri = event.get("mediaUrl") or event.get("s3_uri", "")

    # When the segment-frame container ran before this Lambda it writes both
    # the parsed segments and the pre-computed frame embeddings to a single S3
    # JSON file.  Reading segments from there avoids re-fetching and re-parsing
    # the transcript a second time.  If the container key is absent we fall back
    # to the original transcript-fetch path.
    frame_count      = 0
    frame_emb_bucket = event.get("bucket")
    frame_emb_key    = event.get("frameEmbeddingsKey")

    if frame_emb_bucket and frame_emb_key:
        resp = _s3.get_object(Bucket=frame_emb_bucket, Key=frame_emb_key)
        container_data = json.loads(resp["Body"].read())
        segments = [
            (s["start_s"], s["speaker"], s["text"])
            for s in container_data["segments"]
        ]
        frame_emb_data = container_data["frame_embeddings"]
        print(f"Loaded {len(segments)} segments from container output (transcript fetch skipped)")
    else:
        transcript_url = event.get("transcriptUrl")
        if not transcript_url:
            raise ValueError("transcriptUrl is required but was not found in the event")
        segments = fetch_and_parse_transcript(transcript_url)
        frame_emb_data = []
        print(f"Parsed {len(segments)} speaker segments from transcript")

    model_id = Model(EMBEDDING_MODEL_ID)
    embeddings = generate_text_embeddings(
        segments,
        source_uri=media_uri,
        model_id=model_id,
        embedding_dim=EMBEDDING_DIM,
    )
    print(f"Generated {len(embeddings)} embeddings")

    # Derive user_id from the email embedded in the S3 key.
    # Key format: s3://bucket/{timestamp}/{email}/{filename}
    # Splitting on '/' gives: ['s3:', '', bucket, timestamp, email, filename]
    uri_parts = media_uri.split('/')
    email = uri_parts[4] if len(uri_parts) >= 5 else None
    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"mailto:{email}")) if email else None

    lecture_id = upsert_lecture(media_uri, user_id)
    print(f"Upserted lecture {lecture_id} for user {email or 'unknown'}")

    segment_records = insert_segments(lecture_id, segments)
    print(f"Upserted {len(segment_records)} segments")

    insert_embeddings(segment_records, embeddings, EMBEDDING_MODEL_ID)
    print(f"Inserted {len(embeddings)} embedding vectors")

    if frame_emb_data:
        insert_frame_embeddings(segment_records, frame_emb_data, FRAME_EMBEDDING_MODEL_ID)
        frame_count = len(frame_emb_data)
        print(f"Inserted {frame_count} frame embedding vectors")

    return {
        "statusCode":          200,
        "lectureId":           lecture_id,
        "segmentCount":        len(segments),
        "embeddingCount":      len(embeddings),
        "frameEmbeddingCount": frame_count,
    }