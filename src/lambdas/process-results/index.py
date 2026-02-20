import json
import os

from transcript_utils import fetch_and_parse_transcript
from bedrock_utils import generate_text_embeddings

EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))


def handler(event, context):
    """
    Generate text embeddings from an Amazon Transcribe transcript.

    Expected event keys (provided by Step Functions after process-transcribe
    signals task success):
        transcriptUrl  — HTTPS URL of the Transcribe JSON output on S3
        mediaUrl       — S3 URI of the source video (used as source metadata)

    Embeddings are generated via Bedrock (Titan Embed Text v2) but are not
    yet persisted; database storage will be added in a future iteration.
    Only summary counts are returned so the Step Functions state stays small.
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

    if embeddings:
        sample = embeddings[0]
        print(
            f"Sample — speaker: {sample['speaker']}, "
            f"dim: {len(sample['embedding'])}, "
            f"text[:80]: {sample['text'][:80]!r}"
        )

    return {
        "statusCode":     200,
        "segmentCount":   len(segments),
        "embeddingCount": len(embeddings),
    }
