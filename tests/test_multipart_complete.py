"""Unit tests for lambdas/multipart-complete/index.py (POST /multipart/complete)."""

import boto3
from moto import mock_aws

from conftest import TEST_BUCKET, load_lambda, make_event, parse_body

FILE_KEY = "2024-01-01T12:00:00/user-123/lecture.mp4"


@mock_aws
class TestMultipartComplete:
    def setup_method(self, method):
        """Set up S3 bucket and create a multipart upload before each test."""
        # Create a real (mocked) S3 bucket
        self.s3 = boto3.client('s3', region_name='us-east-1')
        self.s3.create_bucket(Bucket=TEST_BUCKET)

        # Create a multipart upload to get a real upload ID
        response = self.s3.create_multipart_upload(
            Bucket=TEST_BUCKET,
            Key=FILE_KEY,
            ContentType='video/mp4'
        )
        self.upload_id = response['UploadId']

        # Upload two parts to simulate a real multipart upload
        # Moto requires actual part uploads before completing
        # S3 requires each part (except the last) to be at least 5 MB
        MIN_PART_SIZE = 5 * 1024 * 1024  # 5 MB
        part1 = self.s3.upload_part(
            Bucket=TEST_BUCKET,
            Key=FILE_KEY,
            PartNumber=1,
            UploadId=self.upload_id,
            Body=b'0' * MIN_PART_SIZE  # 5 MB of zeros
        )
        part2 = self.s3.upload_part(
            Bucket=TEST_BUCKET,
            Key=FILE_KEY,
            PartNumber=2,
            UploadId=self.upload_id,
            Body=b'1' * MIN_PART_SIZE  # 5 MB of ones (last part can be smaller but we use 5MB for consistency)
        )

        # Store the ETags for completing the upload
        self.parts = [
            {"PartNumber": 1, "ETag": part1['ETag']},
            {"PartNumber": 2, "ETag": part2['ETag']},
        ]

        # Load the lambda module fresh for each test
        self.mod = load_lambda("multipart-complete")

    def test_returns_file_key_and_location(self):
        body = {
            "fileKey": FILE_KEY,
            "uploadId": self.upload_id,
            "parts": self.parts,
        }
        resp = self.mod.handler(make_event(body), {})

        assert resp["statusCode"] == 200
        result = parse_body(resp)
        assert result["fileKey"] == FILE_KEY
        assert result["location"]  # Location is returned
        assert TEST_BUCKET in result["location"]

    def test_completed_upload_creates_object(self):
        """Verify that completing the upload actually creates the S3 object."""
        body = {
            "fileKey": FILE_KEY,
            "uploadId": self.upload_id,
            "parts": self.parts,
        }
        resp = self.mod.handler(make_event(body), {})

        assert resp["statusCode"] == 200

        # Verify the object exists in S3
        objects = self.s3.list_objects_v2(Bucket=TEST_BUCKET, Prefix=FILE_KEY)
        assert objects['KeyCount'] == 1
        assert objects['Contents'][0]['Key'] == FILE_KEY

    def test_missing_file_key_rejected(self):
        body = {
            "uploadId": self.upload_id,
            "parts": self.parts,
        }
        resp = self.mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_missing_upload_id_rejected(self):
        body = {
            "fileKey": FILE_KEY,
            "parts": self.parts,
        }
        resp = self.mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_missing_parts_rejected(self):
        body = {
            "fileKey": FILE_KEY,
            "uploadId": self.upload_id,
        }
        resp = self.mod.handler(make_event(body), {})
        assert resp["statusCode"] == 400

    def test_cors_preflight_returns_200(self):
        resp = self.mod.handler({"httpMethod": "OPTIONS"}, {})
        assert resp["statusCode"] == 200

    def test_cors_header_present_on_every_response(self):
        body = {
            "fileKey": FILE_KEY,
            "uploadId": self.upload_id,
            "parts": self.parts,
        }
        resp = self.mod.handler(make_event(body), {})
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
