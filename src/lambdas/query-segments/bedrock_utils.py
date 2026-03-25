import json

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