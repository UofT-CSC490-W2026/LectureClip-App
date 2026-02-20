"""
Utilities for downloading and parsing Amazon Transcribe output into
speaker-attributed text chunks suitable for embedding.

Adapted from:
github.com/build-on-aws/langchain-embeddings (03-audio-video-workflow)
"""

import json
import math
from urllib.parse import unquote

import boto3

s3 = boto3.client("s3")

# Flush a speaker chunk once it exceeds this length AND ends on a sentence
# boundary, keeping individual embeddings at a manageable token count.
_MAX_CHUNK_CHARS = 1000


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def _s3_coords_from_url(url):
    """
    Convert an Amazon Transcribe transcript HTTPS URL to (bucket, key).

    Transcribe always returns path-style URLs:
        https://s3.<region>.amazonaws.com/<bucket>/<key>
    """
    host_and_path = url.split("//", 1)[-1]        # strip https: scheme
    _, bucket, key = host_and_path.split("/", 2)  # strip S3 hostname
    return bucket, key


def fetch_transcript_json(transcript_url):
    """Download the Transcribe JSON result from S3 and return it as a dict."""
    bucket, key = _s3_coords_from_url(transcript_url)
    key = unquote(key)  # Handle URL-encoded keys (e.g. spaces as %20)
    resp = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(resp["Body"].read())


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------

def _process_items(items):
    """
    Convert a Transcribe items list into (second, speaker, text) tuples.

    Punctuation tokens are attached directly to the preceding word so that
    embeddings include natural sentence endings without losing any content.
    """
    result = []
    for item in items:
        content = item["alternatives"][0]["content"]
        if item["type"] == "punctuation":
            if result:
                sec, spk, txt = result[-1]
                result[-1] = (sec, spk, txt + content)
        else:
            sec = math.floor(float(item["start_time"]))
            spk = item.get("speaker_label", "spk_0")
            result.append((sec, spk, content))
    return result


def _combine_by_speaker(items):
    """
    Group consecutive tokens from the same speaker into chunks.

    A new chunk starts when the speaker changes.  An in-progress chunk is also
    flushed early when it exceeds _MAX_CHUNK_CHARS and ends on a sentence
    boundary (.  !  ?), preventing overly long embeddings.

    A short trailing chunk (< 100 chars) is merged into the previous one to
    avoid orphan fragments with poor embedding signal.
    """
    chunks = []
    cur_sec = cur_spk = cur_txt = None

    for sec, spk, txt in items:
        if cur_spk is None:
            cur_sec, cur_spk, cur_txt = sec, spk, txt
            continue

        if spk == cur_spk:
            cur_txt = f"{cur_txt} {txt}"
            if (
                len(cur_txt) > _MAX_CHUNK_CHARS
                and cur_txt.rstrip().endswith((".", "!", "?"))
            ):
                chunks.append((cur_sec, cur_spk, cur_txt))
                cur_sec, cur_spk, cur_txt = sec, spk, txt
        else:
            chunks.append((cur_sec, cur_spk, cur_txt))
            cur_sec, cur_spk, cur_txt = sec, spk, txt

    if cur_txt is not None:
        if len(cur_txt) < 100 and chunks and chunks[-1][1] == cur_spk:
            # Merge a short trailing fragment into the previous chunk only when
            # it's from the same speaker, to avoid cross-speaker contamination.
            last = chunks.pop()
            chunks.append((last[0], last[1], f"{last[2]} {cur_txt}"))
        else:
            chunks.append((cur_sec, cur_spk, cur_txt))

    return chunks


def parse_transcript(transcript_json):
    """
    Parse an Amazon Transcribe result dict into a list of
    (start_second, speaker_label, text) tuples — one per speaker chunk.
    """
    items = transcript_json["results"]["items"]
    processed = _process_items(items)
    return _combine_by_speaker(processed)


def fetch_and_parse_transcript(transcript_url):
    """Download from S3 and return speaker-chunked segments."""
    data = fetch_transcript_json(transcript_url)
    return parse_transcript(data)
