"""Unit tests for lambdas/multipart-complete/index.py (POST /multipart/complete)."""

from unittest.mock import patch

from conftest import TEST_BUCKET, load_lambda, make_event, parse_body

mod = load_lambda("multipart-complete")

FAKE_FILE_KEY = "2024-01-01T12:00:00/user-123/lecture.mp4"
FAKE_UPLOAD_ID = "mpu-abc123xyz"
FAKE_LOCATION = f"https://s3.amazonaws.com/{TEST_BUCKET}/{FAKE_FILE_KEY}"

VALID_BODY = {
    "fileKey": FAKE_FILE_KEY,
    "uploadId": FAKE_UPLOAD_ID,
    "parts": [
        {"PartNumber": 1, "ETag": "etag-part-1"},
        {"PartNumber": 2, "ETag": "etag-part-2"},
    ],
}


class TestMultipartComplete:
    def test_returns_file_key_and_location(self, mock_s3):
        mock_s3.complete_multipart_upload.return_value = {
            "Location": FAKE_LOCATION,
            "Bucket": TEST_BUCKET,
        }
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(VALID_BODY), {})

        assert resp["statusCode"] == 200
        body = parse_body(resp)
        assert body["fileKey"] == FAKE_FILE_KEY
        assert body["location"] == FAKE_LOCATION

    def test_calls_s3_with_correct_params(self, mock_s3):
        mock_s3.complete_multipart_upload.return_value = {"Location": FAKE_LOCATION}
        with patch.object(mod, "s3_client", mock_s3):
            mod.handler(make_event(VALID_BODY), {})

        mock_s3.complete_multipart_upload.assert_called_once_with(
            Bucket=TEST_BUCKET,
            Key=FAKE_FILE_KEY,
            UploadId=FAKE_UPLOAD_ID,
            MultipartUpload={"Parts": VALID_BODY["parts"]},
        )

    def test_missing_file_key_rejected(self, mock_s3):
        body = {k: v for k, v in VALID_BODY.items() if k != "fileKey"}
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_missing_upload_id_rejected(self, mock_s3):
        body = {k: v for k, v in VALID_BODY.items() if k != "uploadId"}
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_missing_parts_rejected(self, mock_s3):
        body = {k: v for k, v in VALID_BODY.items() if k != "parts"}
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_cors_preflight_returns_200(self, mock_s3):
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler({"httpMethod": "OPTIONS"}, {})
        assert resp["statusCode"] == 200

    def test_cors_header_present_on_every_response(self, mock_s3):
        mock_s3.complete_multipart_upload.return_value = {"Location": FAKE_LOCATION}
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(VALID_BODY), {})
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
