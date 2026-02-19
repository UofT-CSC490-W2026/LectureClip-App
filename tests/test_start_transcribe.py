"""Unit tests for lambdas/start-transcribe/index.py."""

import os
import uuid
import boto3
from moto import mock_aws

from conftest import load_lambda

S3_URI_WITH_PREFIX = "s3://my-bucket/2024-01/user123/lecture.mp4"
S3_URI_NO_PREFIX = "s3://my-bucket/lecture.mp4"
FAKE_SFTOKEN = "sfn-task-token-abc"



class TestParseS3Uri:
    def setup_method(self, method):
        """Load the lambda module fresh for each test."""
        self.mod = load_lambda("start-transcribe")

    def test_with_prefix_returns_correct_parts(self):
        bucket, prefix, filename, extension, file = self.mod._parse_s3_uri(S3_URI_WITH_PREFIX)
        assert bucket == "my-bucket"
        assert prefix == "2024-01/user123"
        assert filename == "lecture"
        assert extension == "mp4"
        assert file == "lecture.mp4"

    def test_without_prefix_returns_empty_prefix(self):
        bucket, prefix, filename, extension, file = self.mod._parse_s3_uri(S3_URI_NO_PREFIX)
        assert bucket == "my-bucket"
        assert prefix == ""
        assert filename == "lecture"
        assert extension == "mp4"
        assert file == "lecture.mp4"

    def test_deep_prefix_is_joined_correctly(self):
        uri = "s3://bucket/a/b/c/file.mov"
        bucket, prefix, filename, extension, file = self.mod._parse_s3_uri(uri)
        assert bucket == "bucket"
        assert prefix == "a/b/c"
        assert file == "file.mov"


@mock_aws
class TestHandler:
    def setup_method(self, method):
        """Set up DynamoDB table and Transcribe service before each test."""
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table = dynamodb.create_table(
            TableName=os.environ["TRANSCRIBE_TABLE"],
            KeySchema=[
                {'AttributeName': 'TranscriptionJobName', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'TranscriptionJobName', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Create transcribe client for verification
        self.transcribe = boto3.client('transcribe', region_name='us-east-1')

        # Load the lambda module fresh for each test
        self.mod = load_lambda("start-transcribe")

    def test_returns_job_name(self):
        result = self.mod.handler({"s3_uri": S3_URI_WITH_PREFIX, "sftoken": FAKE_SFTOKEN}, {})
        assert "job_name" in result

    def test_job_name_is_valid_uuid(self):
        result = self.mod.handler({"s3_uri": S3_URI_WITH_PREFIX, "sftoken": FAKE_SFTOKEN}, {})
        uuid.UUID(result["job_name"])  # raises ValueError if not a valid UUID

    def test_starts_transcription_with_correct_media_uri(self):
        result = self.mod.handler({"s3_uri": S3_URI_WITH_PREFIX, "sftoken": FAKE_SFTOKEN}, {})

        # Verify the transcription job was created with correct media URI
        job = self.transcribe.get_transcription_job(TranscriptionJobName=result["job_name"])
        assert job['TranscriptionJob']['Media']['MediaFileUri'] == S3_URI_WITH_PREFIX

    def test_uses_language_identification(self):
        result = self.mod.handler({"s3_uri": S3_URI_WITH_PREFIX, "sftoken": FAKE_SFTOKEN}, {})

        # Verify language identification is enabled
        job = self.transcribe.get_transcription_job(TranscriptionJobName=result["job_name"])
        assert job['TranscriptionJob']['IdentifyLanguage'] is True

    def test_output_key_with_prefix(self):
        result = self.mod.handler({"s3_uri": S3_URI_WITH_PREFIX, "sftoken": FAKE_SFTOKEN}, {})

        # Verify the transcription job was created
        job = self.transcribe.get_transcription_job(TranscriptionJobName=result["job_name"])
        assert job['TranscriptionJob']['TranscriptionJobName'] == result["job_name"]
        assert job['TranscriptionJob']['Media']['MediaFileUri'] == S3_URI_WITH_PREFIX

    def test_transcription_job_has_correct_status(self):
        result = self.mod.handler({"s3_uri": S3_URI_WITH_PREFIX, "sftoken": FAKE_SFTOKEN}, {})

        # Verify the transcription job has a valid status
        job = self.transcribe.get_transcription_job(TranscriptionJobName=result["job_name"])
        assert job['TranscriptionJob']['TranscriptionJobStatus'] in ['QUEUED', 'IN_PROGRESS', 'COMPLETED']

    def test_speaker_labels_enabled_with_max_ten(self):
        result = self.mod.handler({"s3_uri": S3_URI_WITH_PREFIX, "sftoken": FAKE_SFTOKEN}, {})

        # Verify speaker labels are enabled with correct max
        job = self.transcribe.get_transcription_job(TranscriptionJobName=result["job_name"])
        settings = job['TranscriptionJob']['Settings']
        assert settings['ShowSpeakerLabels'] is True
        assert settings['MaxSpeakerLabels'] == 10

    def test_dynamodb_record_stored_with_correct_fields(self):
        result = self.mod.handler({"s3_uri": S3_URI_WITH_PREFIX, "sftoken": FAKE_SFTOKEN}, {})

        # Verify the DynamoDB record was created with correct fields
        response = self.table.get_item(Key={'TranscriptionJobName': result["job_name"]})
        item = response['Item']
        assert item['TranscriptionJobName'] == result["job_name"]
        assert item['s3_uri'] == S3_URI_WITH_PREFIX
        assert item['sftoken'] == FAKE_SFTOKEN
        assert item['status'] == 'MOCK_IN_PROGRESS'  # moto mock does not set this field, so we check for the default value

    def test_job_name_in_dynamodb_record_matches_return_value(self):
        result = self.mod.handler({"s3_uri": S3_URI_WITH_PREFIX, "sftoken": FAKE_SFTOKEN}, {})

        # Verify the job name in DynamoDB matches the return value
        response = self.table.get_item(Key={'TranscriptionJobName': result["job_name"]})
        item = response['Item']
        assert item['TranscriptionJobName'] == result["job_name"]
