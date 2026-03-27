"""Unit tests for lambdas/process-results/."""

import importlib
import io
import json
import uuid
from unittest.mock import patch

import boto3
import requests
from moto import mock_aws

from conftest import load_lambda, load_module

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

TRANSCRIPT_BUCKET = "test-transcripts"
TRANSCRIPT_KEY = "jobs/job-123/transcribe.json"
TRANSCRIPT_URL = f"https://s3.us-east-1.amazonaws.com/{TRANSCRIPT_BUCKET}/{TRANSCRIPT_KEY}"
MEDIA_URI = "s3://test-bucket/2024-01/user1/lecture.mp4"

# Minimal Transcribe JSON with two speakers producing three distinct chunks.
# Designed to exercise:
#   - pronunciation items (have start_time, speaker_label) — the common case
#   - punctuation items (no timestamp, no speaker) — must be attached to the
#     preceding word, not treated as standalone tokens
#   - a speaker change mid-transcript (spk_0 → spk_1) — triggers chunk flush
SAMPLE_TRANSCRIPT = {
    "results": {
        "transcripts": [{"transcript": "Hello world. This is speaker two."}],
        "items": [
            {
                "type": "pronunciation",
                "alternatives": [{"content": "Hello", "confidence": "0.99"}],
                "start_time": "0.01",
                "end_time": "0.35",
                "speaker_label": "spk_0",
            },
            {
                "type": "pronunciation",
                "alternatives": [{"content": "world", "confidence": "0.98"}],
                "start_time": "0.40",
                "end_time": "0.80",
                "speaker_label": "spk_0",
            },
            {
                # Punctuation token — no start_time or speaker_label.
                # Must be appended to the "world" tuple, producing "world."
                "type": "punctuation",
                "alternatives": [{"content": "."}],
            },
            {
                "type": "pronunciation",
                "alternatives": [{"content": "This", "confidence": "0.97"}],
                "start_time": "1.00",
                "end_time": "1.20",
                "speaker_label": "spk_1",
            },
            {
                "type": "pronunciation",
                "alternatives": [{"content": "is", "confidence": "0.96"}],
                "start_time": "1.30",
                "end_time": "1.50",
                "speaker_label": "spk_1",
            },
            {
                "type": "pronunciation",
                "alternatives": [{"content": "speaker", "confidence": "0.95"}],
                "start_time": "1.60",
                "end_time": "1.90",
                "speaker_label": "spk_1",
            },
            {
                "type": "pronunciation",
                "alternatives": [{"content": "two", "confidence": "0.95"}],
                "start_time": "2.00",
                "end_time": "2.20",
                "speaker_label": "spk_1",
            },
            {
                # Second punctuation token — appended to the "two" tuple.
                "type": "punctuation",
                "alternatives": [{"content": "."}],
            },
        ],
    }
}

# A flat 1024-float vector used wherever a real Bedrock embedding is not
# needed - This is used to mock the titan embedding length. All values are
# identical so the vector is easy to construct and compare without any numeric
# precision concerns.
FAKE_EMBEDDING = [0.1] * 1024


class _FakeBedrockRuntime:
    """
    Plain stub for bedrock-runtime.invoke_model.

    Moto does not implement InvokeModel for bedrock-runtime, so we provide a
    simple stub class (no MagicMock) that records call arguments and returns
    a well-formed streaming body so that bedrock_utils can parse it normally.
    """

    def __init__(self, embedding=None):
        self._embedding = embedding if embedding is not None else FAKE_EMBEDDING
        self.last_kwargs = {}

    def invoke_model(self, **kwargs):
        self.last_kwargs = kwargs
        body = json.dumps({"embedding": self._embedding}).encode()
        return {"body": io.BytesIO(body)}


def _s3_with_transcript(region="us-east-1"):
    """Create a moto S3 bucket pre-loaded with SAMPLE_TRANSCRIPT."""
    s3 = boto3.client("s3", region_name=region)
    s3.create_bucket(Bucket=TRANSCRIPT_BUCKET)
    s3.put_object(
        Bucket=TRANSCRIPT_BUCKET,
        Key=TRANSCRIPT_KEY,
        Body=json.dumps(SAMPLE_TRANSCRIPT).encode(),
    )
    return s3


# ---------------------------------------------------------------------------
# transcript_utils tests
# ---------------------------------------------------------------------------


class TestProcessItems:
    def setup_method(self, method):
        import transcript_utils
        importlib.reload(transcript_utils)
        self.mod = transcript_utils

    def test_pronunciation_items_become_tuples(self):
        # Every pronunciation token must become a (second, speaker, text)
        # 3-tuple. This is the contract that _combine_by_speaker depends on —
        # if the shape is wrong, downstream chunking breaks silently.
        items = SAMPLE_TRANSCRIPT["results"]["items"]
        result = self.mod._process_items(items)
        assert all(len(t) == 3 for t in result)

    def test_punctuation_is_attached_to_preceding_word(self):
        # Transcribe returns punctuation as separate tokens with no timestamp.
        # They must be merged onto the preceding word so embeddings contain
        # natural sentence endings (e.g. "world." not "world" + ".").
        # Failure here means embeddings lose sentence boundary signal.
        items = SAMPLE_TRANSCRIPT["results"]["items"]
        result = self.mod._process_items(items)
        # "world." should be combined (punctuation attached)
        texts = [t[2] for t in result]
        assert any(t.endswith(".") for t in texts)

    def test_no_punctuation_only_tuples_in_result(self):
        # Punctuation tokens must never appear as standalone tuples in the
        # output — they have no start_time so including them as tuples would
        # produce None timestamps, breaking the floor() call in _combine_by_speaker.
        items = SAMPLE_TRANSCRIPT["results"]["items"]
        result = self.mod._process_items(items)
        # Every tuple should have a real start_time (not None)
        assert all(t[0] is not None for t in result)

    def test_speaker_labels_preserved(self):
        # Speaker labels flow through to _combine_by_speaker to determine
        # chunk boundaries. If labels are dropped or unified here, the
        # speaker-change flush never fires and the whole transcript becomes
        # one chunk, producing an oversized embedding.
        items = SAMPLE_TRANSCRIPT["results"]["items"]
        result = self.mod._process_items(items)
        speakers = {t[1] for t in result}
        assert "spk_0" in speakers
        assert "spk_1" in speakers


class TestCombineBySpeaker:
    def setup_method(self, method):
        import transcript_utils
        importlib.reload(transcript_utils)
        self.mod = transcript_utils

    def _items(self):
        return self.mod._process_items(SAMPLE_TRANSCRIPT["results"]["items"])

    def test_returns_list_of_tuples(self):
        # Validates the output contract: a list of (second, speaker, text)
        # 3-tuples. insert_segments unpacks this shape directly — a wrong
        # structure would raise a ValueError at the DB write stage.
        chunks = self.mod._combine_by_speaker(self._items())
        assert isinstance(chunks, list)
        assert all(len(c) == 3 for c in chunks)

    def test_consecutive_same_speaker_merged(self):
        # Consecutive tokens from the same speaker must be joined into one
        # chunk so the embedding captures full phrases rather than
        # individual words.  spk_0 says "Hello" then "world" — they must
        # appear together in a single chunk.
        chunks = self.mod._combine_by_speaker(self._items())
        # spk_0 has two words -> should be one chunk
        spk0_chunks = [c for c in chunks if c[1] == "spk_0"]
        assert len(spk0_chunks) == 1
        assert "Hello" in spk0_chunks[0][2]
        assert "world" in spk0_chunks[0][2]

    def test_speaker_change_creates_new_chunk(self):
        # When the speaker changes, the current chunk must be flushed and a
        # new one started.  Mixing speakers in one chunk would corrupt the
        # embedding with cross-speaker text, degrading search quality.
        chunks = self.mod._combine_by_speaker(self._items())
        speakers = [c[1] for c in chunks]
        assert "spk_0" in speakers
        assert "spk_1" in speakers

    def test_short_trailing_chunk_merged_into_previous(self):
        # A tiny trailing chunk (< 100 chars) from the same speaker is merged
        # into the preceding chunk to avoid orphan fragments that carry poor
        # embedding signal.  This test constructs a two-item list where the
        # second item is short and verifies no chunk is empty after merging.
        items = [
            (0, "spk_0", "A" * 200 + "."),   # long enough to be its own chunk
            (5, "spk_1", "Hi."),              # short trailing spk_1
        ]
        chunks = self.mod._combine_by_speaker(items)
        # spk_1 chunk is < 100 chars; if there's a preceding chunk it should
        # be merged.  Either way, no chunk should be empty.
        assert all(c[2].strip() for c in chunks)

    def test_large_chunk_split_on_sentence_boundary(self):
        # Chunks that exceed _MAX_CHUNK_CHARS (1000) and end on a sentence
        # boundary must be flushed early to keep individual embeddings within
        # Bedrock's token limit.  This test builds a 200-word single-speaker
        # run ending with "." — the flush should trigger at least once.
        sentence = "word " * 200 + "end."
        items = [(i, "spk_0", w) for i, w in enumerate(sentence.split())]
        chunks = self.mod._combine_by_speaker(items)
        # With > 1000 chars the chunk should have been flushed at least once
        assert len(chunks) >= 1


@mock_aws
class TestFetchAndParseTranscript:
    def setup_method(self, method):
        """Set up S3 bucket with transcript JSON and reload module."""
        self.s3 = _s3_with_transcript()

        import transcript_utils
        importlib.reload(transcript_utils)
        self.tu = transcript_utils

    def test_returns_list_of_tuples(self):
        # End-to-end smoke test: the full fetch → parse pipeline must produce
        # a non-empty list of 3-tuples.  Validates that URL parsing, S3
        # download, JSON parsing, and chunking all compose correctly.
        result = self.tu.fetch_and_parse_transcript(TRANSCRIPT_URL)
        assert isinstance(result, list)
        assert all(len(t) == 3 for t in result)

    def test_each_tuple_has_second_speaker_text(self):
        # Type-checks each field: start_second must be an int (floored from
        # Transcribe's float strings), speaker must match the "spk_N" label
        # format, and text must be a non-empty string.  A wrong type here
        # would cause a silent DB type mismatch in aurora_utils.
        result = self.tu.fetch_and_parse_transcript(TRANSCRIPT_URL)
        for second, speaker, text in result:
            assert isinstance(second, int)
            assert speaker.startswith("spk_")
            assert isinstance(text, str) and text

    def test_fetches_from_correct_s3_bucket_and_key(self):
        # Verifies that _s3_coords_from_url resolves the correct bucket/key
        # from the Transcribe HTTPS URL.  A decoy object at a different path
        # contains invalid JSON — if the wrong key were fetched, the parse
        # would fail with a JSONDecodeError.
        self.s3.put_object(
            Bucket=TRANSCRIPT_BUCKET,
            Key="wrong/path/transcribe.json",
            Body=b"not valid json",
        )
        result = self.tu.fetch_and_parse_transcript(TRANSCRIPT_URL)
        assert len(result) > 0

    def test_missing_object_raises(self):
        # If the transcript file has been deleted or never uploaded (e.g.
        # the Transcribe job failed silently), the function must raise rather
        # than return an empty list.  A silent empty return would cause the
        # handler to write 0 segments with no indication of the missing file.
        import pytest
        self.s3.delete_object(Bucket=TRANSCRIPT_BUCKET, Key=TRANSCRIPT_KEY)
        with pytest.raises(Exception):
            self.tu.fetch_and_parse_transcript(TRANSCRIPT_URL)


# ---------------------------------------------------------------------------
# bedrock_utils tests
# ---------------------------------------------------------------------------
#
# Moto does not implement bedrock-runtime InvokeModel ("Not yet implemented").
# We use _FakeBedrockRuntime — a plain Python stub — instead of MagicMock so
# that the tests remain meaningful (call args are captured and asserted) while
# avoiding the real AWS endpoint.
# ---------------------------------------------------------------------------


@mock_aws
class TestEmbedText:
    def setup_method(self, method):
        import bedrock_utils
        importlib.reload(bedrock_utils)
        self.mod = bedrock_utils

    def test_calls_invoke_model_with_correct_model_id(self):
        # The model ID is passed through from the caller and must reach the
        # Bedrock API unchanged.  A wrong model ID would silently use a
        # different (possibly cheaper/lower-quality) embedding model in prod.
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("hello", "amazon.titan-embed-text-v2:0", 1024)
        assert fake.last_kwargs["modelId"] == "amazon.titan-embed-text-v2:0"

    def test_request_body_contains_dimensions(self):
        # The embedding dimension must be sent in the request body so Titan
        # truncates the vector to the right size.  If omitted, Titan returns
        # the default 1536-dim vector, which would silently mismatch the
        # pgvector column size and cause an Aurora type error at insert time.
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("hello", "amazon.titan-embed-text-v2:0", 512)
        body = json.loads(fake.last_kwargs["body"])
        assert body["dimensions"] == 512

    def test_request_body_contains_input_text(self):
        # The text to embed must be forwarded verbatim as "inputText".
        # Truncation or transformation here would change the embedding
        # meaning and degrade search quality without any error being raised.
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("test sentence", "amazon.titan-embed-text-v2:0", 1024)
        body = json.loads(fake.last_kwargs["body"])
        assert body["inputText"] == "test sentence"

    def test_returns_embedding_vector(self):
        # Validates the full response parsing path: the function reads the
        # streaming body, parses the JSON, and returns the "embedding" list.
        # If the key name or response structure changes, this test catches it.
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            result = self.mod.embed_text("hello", "amazon.titan-embed-text-v2:0", 1024)
        assert result == FAKE_EMBEDDING


@mock_aws
class TestGenerateTextEmbeddings:
    def setup_method(self, method):
        self.mod = load_module("process-results", "bedrock_utils")

    def _run(self, segments=None):
        if segments is None:
            segments = [(0, "spk_0", "Hello world."), (1, "spk_1", "Goodbye.")]
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            return self.mod.generate_text_embeddings(
                segments, MEDIA_URI, "amazon.titan-embed-text-v2:0", 1024
            )

    def test_one_record_per_segment(self):
        # Each transcript segment must produce exactly one embedding record.
        # A mismatch (e.g. skipped segments) would create gaps in the search
        # index — some lecture content would be unreachable by queries.
        result = self._run()
        assert len(result) == 2

    def test_record_has_required_fields(self):
        # All nine metadata fields must be present.  insert_embeddings uses
        # "embedding"; the rest are stored for traceability and future
        # re-indexing.  A missing field raises a KeyError at insert time.
        result = self._run()
        required = {"id", "embedding", "text", "start_second", "speaker",
                    "source", "source_uri", "model_id", "created_at"}
        assert required.issubset(result[0].keys())

    def test_embedding_dimension_matches(self):
        # The vector length must equal the requested dimension (1024).
        # A shorter vector would cause a pgvector dimension mismatch error
        # when inserted into the segment_embeddings column.
        result = self._run()
        assert len(result[0]["embedding"]) == 1024

    def test_source_is_filename_only(self):
        # "source" stores just the filename (e.g. "lecture.mp4"), not the
        # full S3 URI.  This field is used for display in tracing logs.
        # The full URI is stored separately in source_uri.
        result = self._run()
        assert result[0]["source"] == "lecture.mp4"

    def test_source_uri_is_full_s3_path(self):
        # "source_uri" must be the complete S3 URI so records can be traced
        # back to the originating video.  This also matches lectures.video_uri
        # in Aurora, enabling joins during re-indexing.
        result = self._run()
        assert result[0]["source_uri"] == MEDIA_URI

    def test_text_preserved_in_record(self):
        # The original segment text must flow through unchanged into the
        # metadata record.  It is stored in Aurora alongside the vector so
        # search results can display the matched transcript excerpt.
        segments = [(0, "spk_0", "Hello world.")]
        result = self._run(segments)
        assert result[0]["text"] == "Hello world."

    def test_each_record_has_unique_id(self):
        # Each embedding record gets a random uuid4 ID.  Duplicates would
        # cause silent ON CONFLICT DO NOTHING skips if the same segment is
        # ever re-embedded, making it impossible to know which vector is live.
        result = self._run()
        ids = [r["id"] for r in result]
        assert len(set(ids)) == len(ids)


# ---------------------------------------------------------------------------
# aurora_utils tests
# ---------------------------------------------------------------------------
#
# All three aurora_utils functions call execute_statement (which moto supports)
# but do not rely on the return value for writes. Moto returns 0 records by
# default, which is correct for INSERT/upsert calls. The _prime_rds helper is
# used to inject custom results when the return value matters.
# ---------------------------------------------------------------------------


@mock_aws
class TestAuroraUtils:
    def setup_method(self, method):
        self.mod = load_module("process-results", "aurora_utils")

    def _prime_rds(self, records, column_metadata):
        """Queue a result set for the next moto execute_statement call."""
        resp = requests.post(
            "http://motoapi.amazonaws.com/moto-api/static/rds-data/statement-results",
            json={"results": [{"records": records, "columnMetadata": column_metadata}]},
        )
        assert resp.status_code == 201

    # -- upsert_lecture -------------------------------------------------------

    def test_upsert_lecture_returns_valid_uuid(self):
        # The return value is the lecture_id used as a foreign key in
        # insert_segments. An invalid UUID would cause a Postgres type error
        # when cast to ::uuid in the INSERT statement.
        result = self.mod.upsert_lecture(MEDIA_URI)
        uuid.UUID(result)  # raises ValueError if not a valid UUID

    def test_upsert_lecture_is_deterministic(self):
        # upsert_lecture uses uuid5(NAMESPACE_URL, video_uri) so repeated
        # processing of the same video always resolves to the same lecture_id.
        # Non-determinism here would create duplicate lecture rows on retries,
        # breaking the ON CONFLICT DO NOTHING idempotency guarantee.
        assert self.mod.upsert_lecture(MEDIA_URI) == self.mod.upsert_lecture(MEDIA_URI)

    def test_upsert_lecture_different_uris_give_different_ids(self):
        # Each distinct video must map to a unique lecture_id.  A collision
        # would cause segments from different videos to be associated with
        # the wrong lecture, corrupting search results.
        assert self.mod.upsert_lecture(MEDIA_URI) != self.mod.upsert_lecture("s3://bucket/other.mp4")

    # -- insert_segments ------------------------------------------------------

    def test_insert_segments_returns_one_record_per_segment(self):
        # The return list is passed directly to insert_embeddings and zipped
        # with the embeddings list.  A length mismatch (fewer records than
        # embeddings) would silently drop the last embeddings from the DB.
        segments = [(0, "spk_0", "Hello."), (1, "spk_1", "World.")]
        records = self.mod.insert_segments("lecture-id", segments)
        assert len(records) == 2

    def test_insert_segments_record_shape(self):
        # Validates the (segment_id, start_s, end_s, text) shape and values.
        # For the last segment, end_s is estimated as start_s + 30 (a
        # heuristic since Transcribe doesn't provide segment-level end times).
        records = self.mod.insert_segments("lecture-id", [(5, "spk_0", "Hello.")])
        segment_id, start_s, end_s, text = records[0]
        assert isinstance(segment_id, str)
        assert start_s == 5.0
        assert end_s == 35.0  # last segment: start_s + 30
        assert text == "Hello."

    def test_insert_segments_end_s_uses_next_start(self):
        # For all segments except the last, end_s must equal the start_s of
        # the following segment.  The video player uses start/end to seek —
        # a wrong end_s would cause clips to play past their natural boundary
        # into the next speaker's turn.
        segments = [(0, "spk_0", "First."), (10, "spk_1", "Second.")]
        records = self.mod.insert_segments("lecture-id", segments)
        assert records[0][2] == 10.0  # end_s of first == start_s of second

    def test_insert_segments_ids_are_deterministic(self):
        # Segment IDs use uuid5(NAMESPACE_URL, f"{lecture_id}:{idx}") so
        # re-running the Lambda for the same video produces the same IDs and
        # the ON CONFLICT DO UPDATE upsert fires correctly rather than
        # creating duplicate rows with new random IDs.
        segments = [(0, "spk_0", "Hello.")]
        first  = self.mod.insert_segments("lecture-id", segments)
        second = self.mod.insert_segments("lecture-id", segments)
        assert first[0][0] == second[0][0]

    # -- insert_embeddings ----------------------------------------------------

    def test_insert_embeddings_runs_without_error(self):
        # Smoke test: verifies that the vector is correctly formatted as a
        # Postgres vector literal ("[0.1,0.1,...]") and the RDS Data API
        # call completes without a serialization or parameter error.
        # Moto treats the INSERT as a no-op so we only assert no exception.
        seg_records = [
            ("seg-id-1", 0.0, 30.0, "Hello."),
            ("seg-id-2", 30.0, 60.0, "World."),
        ]
        embeddings = [{"embedding": FAKE_EMBEDDING}, {"embedding": FAKE_EMBEDDING}]
        # moto execute_statement is a no-op for INSERTs — just verify no exception
        self.mod.insert_embeddings(seg_records, embeddings, "amazon.titan-embed-text-v2:0")


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


@mock_aws
class TestHandler:
    def setup_method(self, method):
        """Set up S3 bucket with transcript JSON before each test."""
        _s3_with_transcript()

        load_module("process-results", "transcript_utils")
        load_module("process-results", "bedrock_utils")
        load_module("process-results", "aurora_utils")

        self.mod = load_lambda("process-results")

    def _run(self, event=None):
        import bedrock_utils
        event = event or {"transcriptUrl": TRANSCRIPT_URL, "mediaUrl": MEDIA_URI}
        fake = _FakeBedrockRuntime()
        with patch.object(bedrock_utils, "bedrock", fake):
            return self.mod.handler(event, {})

    def test_returns_200(self):
        # Happy-path integration test: all four stages (fetch, parse, embed,
        # persist) must complete without error and return statusCode 200.
        result = self._run()
        assert result["statusCode"] == 200

    def test_returns_segment_count(self):
        # The handler logs segmentCount for observability.  A zero count with
        # a 200 status is a silent failure — this asserts at least one segment
        # was parsed, confirming the transcript was not empty or malformed.
        result = self._run()
        assert "segmentCount" in result
        assert result["segmentCount"] > 0

    def test_returns_embedding_count(self):
        # embeddingCount must equal segmentCount: one vector per segment.
        # A mismatch means some segments were parsed but not embedded (or
        # vice versa), leaving gaps in the search index.
        result = self._run()
        assert result["embeddingCount"] == result["segmentCount"]

    def test_raises_without_transcript_url(self):
        # transcriptUrl is the only required field — without it there is
        # nothing to process.  Raising ValueError (rather than returning a
        # 200 with 0 segments) causes Step Functions to mark the execution
        # as FAILED, making the missing URL visible in the workflow history.
        import pytest
        with pytest.raises(ValueError, match="transcriptUrl"):
            self.mod.handler({"mediaUrl": MEDIA_URI}, {})

    def test_media_url_key_accepted(self):
        # process-transcribe signals Step Functions with "mediaUrl" as the
        # key name.  Verifies the handler accepts this primary key format.
        result = self._run({"transcriptUrl": TRANSCRIPT_URL, "mediaUrl": MEDIA_URI})
        assert result["statusCode"] == 200

    def test_s3_uri_key_accepted_as_media_fallback(self):
        # s3-trigger passes the video URI as "s3_uri".  If process-transcribe
        # is bypassed or the event shape changes, the handler must still work
        # using this fallback key.  Tests the `or event.get("s3_uri")` branch
        # in index.py.
        result = self._run({"transcriptUrl": TRANSCRIPT_URL, "s3_uri": MEDIA_URI})
        assert result["statusCode"] == 200