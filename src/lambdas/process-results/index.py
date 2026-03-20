import json
import os

from transcript_utils import fetch_and_parse_transcript
from bedrock_utils import generate_text_embeddings
from aurora_utils import upsert_lecture, insert_segments, insert_embeddings

EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))


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

    transcript_url = event.get("transcriptUrl")
    media_uri = event.get("mediaUrl") or event.get("s3_uri", "")

    if not transcript_url:
        raise ValueError("transcriptUrl is required but was not found in the event")

    segments = fetch_and_parse_transcript(transcript_url)
    print(f"Parsed {len(segments)} speaker segments from transcript")

    embeddings = generate_text_embeddings(
        segments,
        source_uri=media_uri,
        model_id=EMBEDDING_MODEL_ID,
        embedding_dim=EMBEDDING_DIM,
    )
    print(f"Generated {len(embeddings)} embeddings")

    lecture_id = upsert_lecture(media_uri)
    print(f"Upserted lecture {lecture_id}")

    segment_records = insert_segments(lecture_id, segments)
    print(f"Upserted {len(segment_records)} segments")

    insert_embeddings(segment_records, embeddings, EMBEDDING_MODEL_ID)
    print(f"Inserted {len(embeddings)} embedding vectors")

    return {
        "statusCode":     200,
        "lectureId":      lecture_id,
        "segmentCount":   len(segments),
        "embeddingCount": len(embeddings),
    }