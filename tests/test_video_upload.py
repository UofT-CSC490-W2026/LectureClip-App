"""Unit tests for lambdas/video-upload/index.py (POST /upload)."""

import boto3
from moto import mock_aws
from urllib.parse import unquote

from conftest import TEST_BUCKET, TEST_USER_ID, load_lambda, make_event, parse_body

PRESIGNED_URL_EXPIRY = 300  # 5 minutes — must match the Lambda constant

VALID_BODY = {
    "filename": "lecture.mp4",
    "userId": TEST_USER_ID,
    "contentType": "video/mp4",
}


@mock_aws
class TestVideoUpload:
    def setup_method(self, method):
        """Set up S3 bucket before each test."""
        # Create a real (mocked) S3 bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket=TEST_BUCKET)

        # Load the lambda module fresh for each test
        # This ensures it picks up the mocked boto3 client
        self.mod = load_lambda("video-upload")

    def test_returns_upload_url_and_file_key(self):
        resp = self.mod.handler(make_event(VALID_BODY), {})

        assert resp["statusCode"] == 200
        body = parse_body(resp)
        # The presigned URL should contain the bucket name
        assert TEST_BUCKET in body["uploadUrl"]
        assert TEST_USER_ID in body["fileKey"]
        assert "lecture.mp4" in body["fileKey"]

    def test_presigned_url_contains_correct_params(self):
        resp = self.mod.handler(make_event(VALID_BODY), {})

        assert resp["statusCode"] == 200
        body = parse_body(resp)

        # Verify the URL contains expected parameters
        url = body["uploadUrl"]
        assert TEST_BUCKET in url
        # URL-decode the presigned URL to compare with the fileKey (colons are encoded as %3A)
        assert body["fileKey"] in unquote(url)
        # Presigned URLs contain ContentType as a query parameter
        assert "ContentType" in url or "content-type" in url.lower()

    def test_all_allowed_video_types_accepted(self):
        for content_type in [
            "video/mp4",
            "video/mov",
        ]:
            body = {**VALID_BODY, "contentType": content_type}
            resp = self.mod.handler(make_event(body), {})
            assert resp["statusCode"] == 200, f"Expected 200 for {content_type}"

            response_body = parse_body(resp)
            assert "uploadUrl" in response_body
            assert "fileKey" in response_body

    def test_invalid_content_type_rejected(self):
        body = {**VALID_BODY, "contentType": "application/pdf"}
        resp = self.mod.handler(make_event(body), {})

        assert resp["statusCode"] == 400
        assert "Invalid content type" in parse_body(resp)["error"]

    def test_cors_preflight_returns_200(self):
        resp = self.mod.handler({"httpMethod": "OPTIONS"}, {})
        assert resp["statusCode"] == 200

    def test_cors_header_present_on_every_response(self):
        resp = self.mod.handler(make_event(VALID_BODY), {})
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
