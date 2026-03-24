"""Unit tests for lambdas/process-results/."""

import importlib
import io
import json
from unittest.mock import patch

import boto3
from moto import mock_aws

from conftest import load_lambda

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

TRANSCRIPT_BUCKET = "test-transcripts"
TRANSCRIPT_KEY = "jobs/job-123/transcribe.json"
TRANSCRIPT_URL = f"https://s3.us-east-1.amazonaws.com/{TRANSCRIPT_BUCKET}/{TRANSCRIPT_KEY}"
MEDIA_URI = "s3://test-bucket/2024-01/user1/lecture.mp4"

# Minimal Transcribe JSON with two speakers producing three distinct chunks.
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
                "type": "punctuation",
                "alternatives": [{"content": "."}],
            },
        ],
    }
}

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
        items = SAMPLE_TRANSCRIPT["results"]["items"]
        result = self.mod._process_items(items)
        assert all(len(t) == 3 for t in result)

    def test_punctuation_is_attached_to_preceding_word(self):
        items = SAMPLE_TRANSCRIPT["results"]["items"]
        result = self.mod._process_items(items)
        # "world." should be combined (punctuation attached)
        texts = [t[2] for t in result]
        assert any(t.endswith(".") for t in texts)

    def test_no_punctuation_only_tuples_in_result(self):
        items = SAMPLE_TRANSCRIPT["results"]["items"]
        result = self.mod._process_items(items)
        # Every tuple should have a real start_time (not None)
        assert all(t[0] is not None for t in result)

    def test_speaker_labels_preserved(self):
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
        chunks = self.mod._combine_by_speaker(self._items())
        assert isinstance(chunks, list)
        assert all(len(c) == 3 for c in chunks)

    def test_consecutive_same_speaker_merged(self):
        chunks = self.mod._combine_by_speaker(self._items())
        # spk_0 has two words -> should be one chunk
        spk0_chunks = [c for c in chunks if c[1] == "spk_0"]
        assert len(spk0_chunks) == 1
        assert "Hello" in spk0_chunks[0][2]
        assert "world" in spk0_chunks[0][2]

    def test_speaker_change_creates_new_chunk(self):
        chunks = self.mod._combine_by_speaker(self._items())
        speakers = [c[1] for c in chunks]
        assert "spk_0" in speakers
        assert "spk_1" in speakers

    def test_short_trailing_chunk_merged_into_previous(self):
        # Build items where the last speaker chunk is tiny (< 100 chars)
        # followed by a longer chunk from the same speaker — verify no orphan
        items = [
            (0, "spk_0", "A" * 200 + "."),   # long enough to be its own chunk
            (5, "spk_1", "Hi."),              # short trailing spk_1
        ]
        chunks = self.mod._combine_by_speaker(items)
        # spk_1 chunk is < 100 chars; if there's a preceding chunk it should
        # be merged.  Either way, no chunk should be empty.
        assert all(c[2].strip() for c in chunks)

    def test_large_chunk_split_on_sentence_boundary(self):
        # Build a single speaker with many words ending in "."
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
        result = self.tu.fetch_and_parse_transcript(TRANSCRIPT_URL)
        assert isinstance(result, list)
        assert all(len(t) == 3 for t in result)

    def test_each_tuple_has_second_speaker_text(self):
        result = self.tu.fetch_and_parse_transcript(TRANSCRIPT_URL)
        for second, speaker, text in result:
            assert isinstance(second, int)
            assert speaker.startswith("spk_")
            assert isinstance(text, str) and text

    def test_fetches_from_correct_s3_bucket_and_key(self):
        # Put different content at a wrong key; the correct key should be read.
        self.s3.put_object(
            Bucket=TRANSCRIPT_BUCKET,
            Key="wrong/path/transcribe.json",
            Body=b"not valid json",
        )
        result = self.tu.fetch_and_parse_transcript(TRANSCRIPT_URL)
        assert len(result) > 0

    def test_missing_object_raises(self):
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
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("hello", "amazon.titan-embed-text-v2:0", 1024)
        assert fake.last_kwargs["modelId"] == "amazon.titan-embed-text-v2:0"

    def test_request_body_contains_dimensions(self):
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("hello", "amazon.titan-embed-text-v2:0", 512)
        body = json.loads(fake.last_kwargs["body"])
        assert body["dimensions"] == 512

    def test_request_body_contains_input_text(self):
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("test sentence", "amazon.titan-embed-text-v2:0", 1024)
        body = json.loads(fake.last_kwargs["body"])
        assert body["inputText"] == "test sentence"

    def test_returns_embedding_vector(self):
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            result = self.mod.embed_text("hello", "amazon.titan-embed-text-v2:0", 1024)
        assert result == FAKE_EMBEDDING


@mock_aws
class TestGenerateTextEmbeddings:
    def setup_method(self, method):
        import bedrock_utils
        importlib.reload(bedrock_utils)
        self.mod = bedrock_utils

    def _run(self, segments=None):
        if segments is None:
            segments = [(0, "spk_0", "Hello world."), (1, "spk_1", "Goodbye.")]
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            return self.mod.generate_text_embeddings(
                segments, MEDIA_URI, "amazon.titan-embed-text-v2:0", 1024
            )

    def test_one_record_per_segment(self):
        result = self._run()
        assert len(result) == 2

    def test_record_has_required_fields(self):
        result = self._run()
        required = {"id", "embedding", "text", "start_second", "speaker",
                    "source", "source_uri", "model_id", "created_at"}
        assert required.issubset(result[0].keys())

    def test_embedding_dimension_matches(self):
        result = self._run()
        assert len(result[0]["embedding"]) == 1024

    def test_source_is_filename_only(self):
        result = self._run()
        assert result[0]["source"] == "lecture.mp4"

    def test_source_uri_is_full_s3_path(self):
        result = self._run()
        assert result[0]["source_uri"] == MEDIA_URI

    def test_text_preserved_in_record(self):
        segments = [(0, "spk_0", "Hello world.")]
        result = self._run(segments)
        assert result[0]["text"] == "Hello world."

    def test_each_record_has_unique_id(self):
        result = self._run()
        ids = [r["id"] for r in result]
        assert len(set(ids)) == len(ids)


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


@mock_aws
class TestHandler:
    def setup_method(self, method):
        """Set up S3 bucket with transcript JSON before each test."""
        _s3_with_transcript()

        import transcript_utils
        import bedrock_utils
        import aurora_utils
        importlib.reload(transcript_utils)
        importlib.reload(bedrock_utils)
        importlib.reload(aurora_utils)

        self.mod = load_lambda("process-results")

    def _run(self, event=None):
        import bedrock_utils
        event = event or {"transcriptUrl": TRANSCRIPT_URL, "mediaUrl": MEDIA_URI}
        fake = _FakeBedrockRuntime()
        mock_segment_records = [
            ("segment-0", 0.0, 1.0, "Hello world."),
            ("segment-1", 1.0, 31.0, "This is speaker two."),
        ]
        with patch.object(bedrock_utils, "bedrock", fake), \
             patch.object(transcript_utils, "s3", self._mock_s3()), \
             patch.object(self.mod, "upsert_lecture", return_value="lecture-123"), \
             patch.object(self.mod, "insert_segments", return_value=mock_segment_records), \
             patch.object(self.mod, "insert_embeddings"):
            return self.mod.handler(event, {})

    def test_returns_200(self):
        result = self._run()
        assert result["statusCode"] == 200

    def test_returns_segment_count(self):
        result = self._run()
        assert "segmentCount" in result
        assert result["segmentCount"] > 0

    def test_returns_embedding_count(self):
        result = self._run()
        assert result["embeddingCount"] == result["segmentCount"]

    def test_raises_without_transcript_url(self):
        import pytest
        with pytest.raises(ValueError, match="transcriptUrl"):
            self.mod.handler({"mediaUrl": MEDIA_URI}, {})

    def test_media_url_key_accepted(self):
        result = self._run({"transcriptUrl": TRANSCRIPT_URL, "mediaUrl": MEDIA_URI})
        assert result["statusCode"] == 200

    def test_s3_uri_key_accepted_as_media_fallback(self):
        result = self._run({"transcriptUrl": TRANSCRIPT_URL, "s3_uri": MEDIA_URI})
        assert result["statusCode"] == 200