"""Unit tests for lambdas/video-upload/index.py (POST /upload)."""

from unittest.mock import patch

from conftest import TEST_BUCKET, TEST_USER_ID, load_lambda, make_event, parse_body

mod = load_lambda("video-upload")

PRESIGNED_URL_EXPIRY = 300  # 5 minutes — must match the Lambda constant
FAKE_URL = "https://s3.amazonaws.com/presigned-put-url"

VALID_BODY = {
    "filename": "lecture.mp4",
    "userId": TEST_USER_ID,
    "contentType": "video/mp4",
}


class TestVideoUpload:
    def test_returns_upload_url_and_file_key(self, mock_s3):
        mock_s3.generate_presigned_url.return_value = FAKE_URL
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(VALID_BODY), {})

        assert resp["statusCode"] == 200
        body = parse_body(resp)
        assert body["uploadUrl"] == FAKE_URL
        assert TEST_USER_ID in body["fileKey"]
        assert "lecture.mp4" in body["fileKey"]

    def test_presigned_url_uses_correct_params(self, mock_s3):
        mock_s3.generate_presigned_url.return_value = FAKE_URL
        with patch.object(mod, "s3_client", mock_s3):
            mod.handler(make_event(VALID_BODY), {})

        call = mock_s3.generate_presigned_url.call_args
        assert call.args[0] == "put_object"
        assert call.kwargs["Params"]["Bucket"] == TEST_BUCKET
        assert call.kwargs["Params"]["ContentType"] == "video/mp4"
        assert call.kwargs["ExpiresIn"] == PRESIGNED_URL_EXPIRY

    def test_all_allowed_video_types_accepted(self, mock_s3):
        mock_s3.generate_presigned_url.return_value = FAKE_URL
        for content_type in [
            "video/mp4",
            "video/mov",
        ]:
            body = {**VALID_BODY, "contentType": content_type}
            with patch.object(mod, "s3_client", mock_s3):
                resp = mod.handler(make_event(body), {})
            assert resp["statusCode"] == 200, f"Expected 200 for {content_type}"

    def test_invalid_content_type_rejected(self, mock_s3):
        body = {**VALID_BODY, "contentType": "application/pdf"}
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(body), {})

        assert resp["statusCode"] == 400
        assert "Invalid content type" in parse_body(resp)["error"]

    def test_cors_preflight_returns_200(self, mock_s3):
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler({"httpMethod": "OPTIONS"}, {})
        assert resp["statusCode"] == 200

    def test_cors_header_present_on_every_response(self, mock_s3):
        mock_s3.generate_presigned_url.return_value = FAKE_URL
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(VALID_BODY), {})
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
