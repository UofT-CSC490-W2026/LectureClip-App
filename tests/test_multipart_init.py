"""Unit tests for lambdas/multipart-init/index.py (POST /multipart/init)."""

import math
import boto3
from moto import mock_aws

from conftest import TEST_USER_ID, load_lambda, make_event, parse_body, TEST_BUCKET

PART_SIZE = 100 * 1024 * 1024       # 100 MB — must match the Lambda constant
PRESIGNED_URL_EXPIRY = 3600          # 1 hour — must match the Lambda constant

VALID_BODY = {
    "filename": "large-lecture.mp4",
    "userId": TEST_USER_ID,
    "contentType": "video/mp4",
    "fileSize": 3 * PART_SIZE,  # 300 MB → exactly 3 parts
}


@mock_aws
class TestMultipartInit:
    def setup_method(self, method):
        """Set up S3 bucket before each test."""
        # Create a real (mocked) S3 bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket=TEST_BUCKET)

        # Load the lambda module fresh for each test
        # This ensures it picks up the mocked boto3 client
        self.mod = load_lambda("multipart-init")

    def test_returns_upload_id_and_file_key(self):
        resp = self.mod.handler(make_event(VALID_BODY), {})

        assert resp["statusCode"] == 200
        body = parse_body(resp)
        # Moto generates a real upload ID
        assert "uploadId" in body
        assert body["uploadId"]  # Not empty
        assert TEST_USER_ID in body["fileKey"]
        assert "large-lecture.mp4" in body["fileKey"]

    def test_part_count_matches_file_size(self):
        file_size = int(2.5 * PART_SIZE)  # 250 MB → ceil → 3 parts
        body = {**VALID_BODY, "fileSize": file_size}
        resp = self.mod.handler(make_event(body), {})

        parsed = parse_body(resp)
        expected = math.ceil(file_size / PART_SIZE)
        assert parsed["partCount"] == expected
        assert len(parsed["presignedUrls"]) == expected

    def test_part_numbers_are_sequential_from_one(self):
        resp = self.mod.handler(make_event(VALID_BODY), {})

        parts = parse_body(resp)["presignedUrls"]
        assert [p["partNumber"] for p in parts] == list(range(1, len(parts) + 1))

    def test_presigned_url_contains_correct_params(self):
        # Single-part file for simplicity
        body = {**VALID_BODY, "fileSize": PART_SIZE}
        resp = self.mod.handler(make_event(body), {})

        assert resp["statusCode"] == 200
        parsed = parse_body(resp)

        # Verify we got exactly 1 presigned URL
        assert len(parsed["presignedUrls"]) == 1
        url_obj = parsed["presignedUrls"][0]

        # Check the part number
        assert url_obj["partNumber"] == 1

        # Check the URL contains expected components
        url = url_obj["uploadUrl"]
        assert TEST_BUCKET in url
        assert "uploadid" in url.lower()
        assert "partnumber" in url.lower()

    def test_invalid_content_type_rejected(self):
        body = {**VALID_BODY, "contentType": "image/png"}
        resp = self.mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_zero_file_size_rejected(self):
        body = {**VALID_BODY, "fileSize": 0}
        resp = self.mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_cors_preflight_returns_200(self):
        resp = self.mod.handler({"httpMethod": "OPTIONS"}, {})
        assert resp["statusCode"] == 200

    def test_cors_header_present_on_every_response(self):
        resp = self.mod.handler(make_event(VALID_BODY), {})
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
