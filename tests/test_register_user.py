"""Unit tests for lambdas/register-user/."""

import json
import uuid
from unittest.mock import MagicMock, patch

from conftest import load_lambda, parse_body

TEST_EMAIL = "alice@example.com"
EXPECTED_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"mailto:{TEST_EMAIL}"))


def _make_event(body: dict, method: str = "POST") -> dict:
    return {"httpMethod": method, "body": json.dumps(body)}


def _load():
    return load_lambda("register-user")


def _mock_rds(side_effect=None):
    mock = MagicMock()
    if side_effect:
        mock.execute_statement.side_effect = side_effect
    return mock


# ---------------------------------------------------------------------------
# OPTIONS preflight
# ---------------------------------------------------------------------------


class TestOptions:
    def test_options_returns_200(self):
        mod = _load()
        result = mod.handler({"httpMethod": "OPTIONS", "body": None}, {})
        assert result["statusCode"] == 200

    def test_options_cors_headers_present(self):
        mod = _load()
        result = mod.handler({"httpMethod": "OPTIONS", "body": None}, {})
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "POST" in result["headers"]["Access-Control-Allow-Methods"]
        assert "OPTIONS" in result["headers"]["Access-Control-Allow-Methods"]

    def test_options_body_is_empty(self):
        mod = _load()
        result = mod.handler({"httpMethod": "OPTIONS", "body": None}, {})
        assert result["body"] == ""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_missing_email_returns_400(self):
        mod = _load()
        result = mod.handler(_make_event({}), {})
        assert result["statusCode"] == 400

    def test_empty_email_returns_400(self):
        mod = _load()
        result = mod.handler(_make_event({"email": "  "}), {})
        assert result["statusCode"] == 400

    def test_missing_email_error_message(self):
        mod = _load()
        result = mod.handler(_make_event({}), {})
        assert "email" in parse_body(result)["error"].lower()

    def test_invalid_json_body_returns_400(self):
        mod = _load()
        result = mod.handler({"httpMethod": "POST", "body": "not-json"}, {})
        assert result["statusCode"] == 400

    def test_null_body_treated_as_empty_object(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler({"httpMethod": "POST", "body": None}, {})
        assert result["statusCode"] == 400


# ---------------------------------------------------------------------------
# Successful registration
# ---------------------------------------------------------------------------


class TestSuccess:
    def test_returns_200(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler(_make_event({"email": TEST_EMAIL}), {})
        assert result["statusCode"] == 200

    def test_response_contains_user_id(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler(_make_event({"email": TEST_EMAIL}), {})
        assert "userId" in parse_body(result)

    def test_response_contains_email(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler(_make_event({"email": TEST_EMAIL}), {})
        assert parse_body(result)["email"] == TEST_EMAIL

    def test_user_id_is_deterministic_uuid5(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler(_make_event({"email": TEST_EMAIL}), {})
        assert parse_body(result)["userId"] == EXPECTED_USER_ID

    def test_email_is_lowercased(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler(_make_event({"email": "Alice@Example.COM"}), {})
        body = parse_body(result)
        assert body["email"] == "alice@example.com"

    def test_same_email_produces_same_user_id_regardless_of_case(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            r1 = mod.handler(_make_event({"email": "alice@example.com"}), {})
            r2 = mod.handler(_make_event({"email": "ALICE@EXAMPLE.COM"}), {})
        assert parse_body(r1)["userId"] == parse_body(r2)["userId"]

    def test_cors_headers_present_on_success(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler(_make_event({"email": TEST_EMAIL}), {})
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"


# ---------------------------------------------------------------------------
# RDS call details
# ---------------------------------------------------------------------------


class TestRdsCall:
    def test_execute_statement_called_once(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            mod.handler(_make_event({"email": TEST_EMAIL}), {})
        mock_rds.execute_statement.assert_called_once()

    def test_user_id_param_passed_to_rds(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            mod.handler(_make_event({"email": TEST_EMAIL}), {})
        params = {
            p["name"]: p["value"]
            for p in mock_rds.execute_statement.call_args.kwargs["parameters"]
        }
        assert params["user_id"] == {"stringValue": EXPECTED_USER_ID}

    def test_email_param_passed_to_rds(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            mod.handler(_make_event({"email": TEST_EMAIL}), {})
        params = {
            p["name"]: p["value"]
            for p in mock_rds.execute_statement.call_args.kwargs["parameters"]
        }
        assert params["email"] == {"stringValue": TEST_EMAIL}

    def test_display_name_null_when_omitted(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            mod.handler(_make_event({"email": TEST_EMAIL}), {})
        params = {
            p["name"]: p["value"]
            for p in mock_rds.execute_statement.call_args.kwargs["parameters"]
        }
        assert params["display_name"] == {"isNull": True}

    def test_display_name_forwarded_when_provided(self):
        mod = _load()
        mock_rds = _mock_rds()
        with patch.object(mod, "rds_data", mock_rds):
            mod.handler(_make_event({"email": TEST_EMAIL, "displayName": "Alice"}), {})
        params = {
            p["name"]: p["value"]
            for p in mock_rds.execute_statement.call_args.kwargs["parameters"]
        }
        assert params["display_name"] == {"stringValue": "Alice"}


# ---------------------------------------------------------------------------
# Aurora error handling
# ---------------------------------------------------------------------------


class TestAuroraError:
    def test_aurora_error_returns_500(self):
        mod = _load()
        mock_rds = _mock_rds(side_effect=RuntimeError("DB down"))
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler(_make_event({"email": TEST_EMAIL}), {})
        assert result["statusCode"] == 500

    def test_aurora_error_response_has_error_key(self):
        mod = _load()
        mock_rds = _mock_rds(side_effect=RuntimeError("DB down"))
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler(_make_event({"email": TEST_EMAIL}), {})
        assert "error" in parse_body(result)

    def test_aurora_error_cors_headers_still_present(self):
        mod = _load()
        mock_rds = _mock_rds(side_effect=RuntimeError("DB down"))
        with patch.object(mod, "rds_data", mock_rds):
            result = mod.handler(_make_event({"email": TEST_EMAIL}), {})
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"
