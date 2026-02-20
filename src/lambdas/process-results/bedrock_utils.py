"""
Text embedding generation via Amazon Bedrock (Titan Embed Text v2).

Adapted from:
github.com/build-on-aws/langchain-embeddings (03-audio-video-workflow)
"""

import json
import uuid
from datetime import datetime, timezone

import boto3

bedrock = boto3.client("bedrock-runtime")


def embed_text(text, model_id, embedding_dim):
    """
    Call Bedrock and return the embedding vector for *text*.

    Uses the Titan Embed Text v2 request format:
        { "inputText": "...", "dimensions": N, "normalize": true }
    """
    body = json.dumps({
        "inputText": text,
        "dimensions": embedding_dim,
        "normalize": True,
    })
    response = bedrock.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def generate_text_embeddings(segments, source_uri, model_id, embedding_dim):
    """
    Generate an embedding for each (start_second, speaker, text) segment.

    Returns a list of dicts containing the vector and its associated metadata.
    Database storage is intentionally omitted here; the caller receives the
    full list for logging and will persist it in a future iteration.
    """
    filename = source_uri.rsplit("/", 1)[-1] if source_uri else ""
    results = []

    for start_second, speaker, text in segments:
        vector = embed_text(text, model_id, embedding_dim)
        results.append({
            "id":           str(uuid.uuid4()),
            "embedding":    vector,
            "text":         text,
            "start_second": start_second,
            "speaker":      speaker,
            "source":       filename,
            "source_uri":   source_uri,
            "model_id":     model_id,
            "created_at":   datetime.now(timezone.utc).isoformat(),
        })

    return results
