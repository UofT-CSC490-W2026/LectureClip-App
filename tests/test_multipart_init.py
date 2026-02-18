"""Unit tests for lambdas/multipart-init/index.py (POST /multipart/init)."""

import math
from unittest.mock import patch

from conftest import TEST_USER_ID, load_lambda, make_event, parse_body

mod = load_lambda("multipart-init")

PART_SIZE = 100 * 1024 * 1024       # 100 MB — must match the Lambda constant
PRESIGNED_URL_EXPIRY = 3600          # 1 hour — must match the Lambda constant
FAKE_UPLOAD_ID = "mpu-abc123xyz"
FAKE_PART_URL = "https://s3.amazonaws.com/presigned-part-url"

VALID_BODY = {
    "filename": "large-lecture.mp4",
    "userId": TEST_USER_ID,
    "contentType": "video/mp4",
    "fileSize": 3 * PART_SIZE,  # 300 MB → exactly 3 parts
}


class TestMultipartInit:
    def test_returns_upload_id_and_file_key(self, mock_s3):
        mock_s3.create_multipart_upload.return_value = {"UploadId": FAKE_UPLOAD_ID}
        mock_s3.generate_presigned_url.return_value = FAKE_PART_URL
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(VALID_BODY), {})

        assert resp["statusCode"] == 200
        body = parse_body(resp)
        assert body["uploadId"] == FAKE_UPLOAD_ID
        assert TEST_USER_ID in body["fileKey"]
        assert "large-lecture.mp4" in body["fileKey"]

    def test_part_count_matches_file_size(self, mock_s3):
        mock_s3.create_multipart_upload.return_value = {"UploadId": FAKE_UPLOAD_ID}
        mock_s3.generate_presigned_url.return_value = FAKE_PART_URL

        file_size = int(2.5 * PART_SIZE)  # 250 MB → ceil → 3 parts
        body = {**VALID_BODY, "fileSize": file_size}
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(body), {})

        parsed = parse_body(resp)
        expected = math.ceil(file_size / PART_SIZE)
        assert parsed["partCount"] == expected
        assert len(parsed["presignedUrls"]) == expected

    def test_part_numbers_are_sequential_from_one(self, mock_s3):
        mock_s3.create_multipart_upload.return_value = {"UploadId": FAKE_UPLOAD_ID}
        mock_s3.generate_presigned_url.return_value = FAKE_PART_URL
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(VALID_BODY), {})

        parts = parse_body(resp)["presignedUrls"]
        assert [p["partNumber"] for p in parts] == list(range(1, len(parts) + 1))

    def test_presigned_url_uses_correct_params(self, mock_s3):
        mock_s3.create_multipart_upload.return_value = {"UploadId": FAKE_UPLOAD_ID}
        mock_s3.generate_presigned_url.return_value = FAKE_PART_URL

        # Single-part file for simplicity
        body = {**VALID_BODY, "fileSize": PART_SIZE}
        with patch.object(mod, "s3_client", mock_s3):
            mod.handler(make_event(body), {})

        call = mock_s3.generate_presigned_url.call_args
        assert call.args[0] == "upload_part"
        assert call.kwargs["Params"]["UploadId"] == FAKE_UPLOAD_ID
        assert call.kwargs["Params"]["PartNumber"] == 1
        assert call.kwargs["ExpiresIn"] == PRESIGNED_URL_EXPIRY

    def test_invalid_content_type_rejected(self, mock_s3):
        body = {**VALID_BODY, "contentType": "image/png"}
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_zero_file_size_rejected(self, mock_s3):
        body = {**VALID_BODY, "fileSize": 0}
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_cors_preflight_returns_200(self, mock_s3):
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler({"httpMethod": "OPTIONS"}, {})
        assert resp["statusCode"] == 200

    def test_cors_header_present_on_every_response(self, mock_s3):
        mock_s3.create_multipart_upload.return_value = {"UploadId": FAKE_UPLOAD_ID}
        mock_s3.generate_presigned_url.return_value = FAKE_PART_URL
        with patch.object(mod, "s3_client", mock_s3):
            resp = mod.handler(make_event(VALID_BODY), {})
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
