"""Unit tests for lambdas/query-segments/."""

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

FAKE_LECTURE_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
FAKE_EMBEDDING  = [0.1] * 1024


class _FakeBedrockRuntime:
    """Plain stub for bedrock-runtime — same pattern as test_process_results."""

    def __init__(self, embedding=None):
        self._embedding = embedding if embedding is not None else FAKE_EMBEDDING
        self.last_kwargs = {}

    def invoke_model(self, **kwargs):
        self.last_kwargs = kwargs
        body = json.dumps({"embedding": self._embedding}).encode()
        return {"body": io.BytesIO(body)}


# ---------------------------------------------------------------------------
# bedrock_utils tests
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

    def test_request_body_contains_input_text(self):
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("lecture on neural nets", "amazon.titan-embed-text-v2:0", 1024)
        body = json.loads(fake.last_kwargs["body"])
        assert body["inputText"] == "lecture on neural nets"

    def test_request_body_contains_dimensions(self):
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            self.mod.embed_text("hello", "amazon.titan-embed-text-v2:0", 512)
        body = json.loads(fake.last_kwargs["body"])
        assert body["dimensions"] == 512

    def test_returns_embedding_vector(self):
        fake = _FakeBedrockRuntime()
        with patch.object(self.mod, "bedrock", fake):
            result = self.mod.embed_text("hello", "amazon.titan-embed-text-v2:0", 1024)
        assert result == FAKE_EMBEDDING


# ---------------------------------------------------------------------------
# aurora_utils tests
# ---------------------------------------------------------------------------


@mock_aws
class TestSearchSegments:
    def setup_method(self, method):
        import aurora_utils
        importlib.reload(aurora_utils)
        self.mod = aurora_utils

    def test_returns_a_list(self):
        # Moto intercepts execute_statement and returns empty records; the
        # function should still return a list without raising.
        result = self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 5)
        assert isinstance(result, list)

    def test_each_result_has_start_and_end(self):
        # With moto returning no real rows this verifies the empty-records path.
        result = self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 5)
        for item in result:
            assert "start" in item
            assert "end" in item

    def test_k_is_forwarded_to_rds(self):
        # Patch rds_data to capture the parameters sent to execute_statement.
        calls = []

        class _FakeRds:
            def execute_statement(self, **kwargs):
                calls.append(kwargs)
                return {"records": [], "columnMetadata": []}

        with patch.object(self.mod, "rds_data", _FakeRds()):
            self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 7)

        params = {p["name"]: p["value"] for p in calls[0]["parameters"]}
        assert params["k"] == {"longValue": 7}

    def test_lecture_id_is_forwarded_to_rds(self):
        calls = []

        class _FakeRds:
            def execute_statement(self, **kwargs):
                calls.append(kwargs)
                return {"records": [], "columnMetadata": []}

        with patch.object(self.mod, "rds_data", _FakeRds()):
            self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 5)

        params = {p["name"]: p["value"] for p in calls[0]["parameters"]}
        assert params["video_uri"] == {"stringValue": FAKE_LECTURE_ID}

    def test_embedding_vector_serialised_as_bracket_notation(self):
        calls = []

        class _FakeRds:
            def execute_statement(self, **kwargs):
                calls.append(kwargs)
                return {"records": [], "columnMetadata": []}

        small_vec = [0.5, -0.3, 1.0]
        with patch.object(self.mod, "rds_data", _FakeRds()):
            self.mod.search_segments(FAKE_LECTURE_ID, small_vec, 5)

        params = {p["name"]: p["value"] for p in calls[0]["parameters"]}
        assert params["vec"] == {"stringValue": "[0.5,-0.3,1.0]"}

    def test_rows_mapped_to_start_end_dicts(self):
        class _FakeRds:
            def execute_statement(self, **kwargs):
                return {
                    "columnMetadata": [
                        {"label": "start_s"},
                        {"label": "end_s"},
                        {"label": "similarity"},
                    ],
                    "records": [
                        [{"doubleValue": 12.0}, {"doubleValue": 28.0}, {"doubleValue": 0.95}],
                        [{"doubleValue": 46.0}, {"doubleValue": 64.0}, {"doubleValue": 0.88}],
                    ],
                }

        with patch.object(self.mod, "rds_data", _FakeRds()):
            result = self.mod.search_segments(FAKE_LECTURE_ID, FAKE_EMBEDDING, 2)

        assert result == [{"start": 12.0, "end": 28.0}, {"start": 46.0, "end": 64.0}]


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


@mock_aws
class TestHandler:
    def setup_method(self, method):
        import bedrock_utils
        import aurora_utils
        importlib.reload(bedrock_utils)
        importlib.reload(aurora_utils)
        self.mod = load_lambda("query-segments")

    def _run(self, body=None):
        import bedrock_utils
        body = body or {"videoId": FAKE_LECTURE_ID, "query": "what is backpropagation"}
        fake = _FakeBedrockRuntime()
        with patch.object(bedrock_utils, "bedrock", fake):
            return self.mod.handler({"body": json.dumps(body)}, {})

    def test_returns_200(self):
        result = self._run()
        assert result["statusCode"] == 200

    def test_response_contains_segments_key(self):
        result = self._run()
        body = json.loads(result["body"])
        assert "segments" in body

    def test_segments_is_a_list(self):
        result = self._run()
        body = json.loads(result["body"])
        assert isinstance(body["segments"], list)

    def test_cors_header_present(self):
        result = self._run()
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_missing_video_id_returns_400(self):
        result = self._run({"query": "backpropagation"})
        assert result["statusCode"] == 400

    def test_missing_query_returns_400(self):
        result = self._run({"videoId": FAKE_LECTURE_ID})
        assert result["statusCode"] == 400

    def test_invalid_json_body_returns_400(self):
        import bedrock_utils
        fake = _FakeBedrockRuntime()
        with patch.object(bedrock_utils, "bedrock", fake):
            result = self.mod.handler({"body": "not json"}, {})
        assert result["statusCode"] == 400

    def test_default_k_is_five(self):
        """Handler must pass k=5 to search_segments when not specified."""
        # Patch the name inside the handler module (imported via `from aurora_utils import`).
        calls = []

        def _spy(lecture_id, embedding, k):
            calls.append(k)
            return []

        with patch.object(self.mod, "search_segments", _spy):
            self._run()

        assert calls == [5]

    def test_custom_k_is_forwarded(self):
        calls = []

        def _spy(lecture_id, embedding, k):
            calls.append(k)
            return []

        with patch.object(self.mod, "search_segments", _spy):
            self._run({"videoId": FAKE_LECTURE_ID, "query": "neural nets", "k": 3})

        assert calls == [3]

    def test_segments_from_aurora_returned_verbatim(self):
        """Whatever search_segments returns is passed through to the response."""
        fake_segments = [{"start": 10.0, "end": 20.0}, {"start": 30.0, "end": 45.0}]

        with patch.object(self.mod, "search_segments", return_value=fake_segments):
            result = self._run()

        body = json.loads(result["body"])
        assert body["segments"] == fake_segments