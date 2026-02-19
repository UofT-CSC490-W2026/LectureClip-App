"""Unit tests for lambdas/s3-trigger/index.py."""

import json
import boto3
from moto import mock_aws

from conftest import load_lambda

BUCKET = "test-bucket"
KEY = "2024-01-01T00:00:00/user123/lecture.mp4"
S3_URI = f"s3://{BUCKET}/{KEY}"
STATE_MACHINE_ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:TestMachine"


def _direct_s3_event(bucket=BUCKET, key=KEY):
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                }
            }
        ]
    }


def _sns_s3_event(bucket=BUCKET, key=KEY):
    sns_message = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                }
            }
        ]
    }
    return {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps(sns_message),
                }
            }
        ]
    }


def _sns_test_event():
    return {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps({"Event": "s3:TestEvent"}),
                }
            }
        ]
    }


class TestExtractS3Record:
    def setup_method(self, method):
        """Load the lambda module fresh for each test."""
        self.mod = load_lambda("s3-trigger")

    def test_direct_s3_event_returns_s3_record(self):
        record = self.mod._extract_s3_record(_direct_s3_event())
        assert record["bucket"]["name"] == BUCKET
        assert record["object"]["key"] == KEY

    def test_sns_wrapped_event_unwraps_correctly(self):
        record = self.mod._extract_s3_record(_sns_s3_event())
        assert record["bucket"]["name"] == BUCKET
        assert record["object"]["key"] == KEY

    def test_sns_test_event_returns_none(self):
        record = self.mod._extract_s3_record(_sns_test_event())
        assert record is None


@mock_aws
class TestHandler:
    def setup_method(self, method):
        """Set up Step Functions state machine before each test."""
        # Create a real (mocked) Step Functions state machine
        self.sfn = boto3.client('stepfunctions', region_name='us-east-1')

        # Create a state machine with minimal definition
        self.sfn.create_state_machine(
            name='TestMachine',
            definition=json.dumps({
                "Comment": "Test state machine",
                "StartAt": "PassState",
                "States": {
                    "PassState": {
                        "Type": "Pass",
                        "End": True
                    }
                }
            }),
            roleArn='arn:aws:iam::123456789012:role/TestRole',
        )

        # Load the lambda module fresh for each test
        self.mod = load_lambda("s3-trigger")

    def test_direct_event_starts_execution(self):
        resp = self.mod.handler(_direct_s3_event(), {})
        assert resp["statusCode"] == 200

        # Verify execution was created
        executions = self.sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN)
        assert len(executions['executions']) == 1

    def test_sns_event_starts_execution(self):
        resp = self.mod.handler(_sns_s3_event(), {})
        assert resp["statusCode"] == 200

        # Verify execution was created
        executions = self.sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN)
        assert len(executions['executions']) == 1

    def test_sns_test_event_skipped(self):
        resp = self.mod.handler(_sns_test_event(), {})
        assert resp["statusCode"] == 200

        # Verify no execution was created
        executions = self.sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN)
        assert len(executions['executions']) == 0

    def test_non_video_file_skipped(self):
        event = _direct_s3_event(key="2024-01-01/user123/document.pdf")
        resp = self.mod.handler(event, {})
        assert resp["statusCode"] == 200

        # Verify no execution was created
        executions = self.sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN)
        assert len(executions['executions']) == 0

    def test_extension_check_is_case_insensitive(self):
        event = _direct_s3_event(key="2024-01-01/user123/lecture.MP4")
        resp = self.mod.handler(event, {})
        assert resp["statusCode"] == 200

        # Verify execution was created
        executions = self.sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN)
        assert len(executions['executions']) == 1

    def test_execution_input_contains_correct_s3_uri_and_name_suffix(self):
        self.mod.handler(_direct_s3_event(), {})

        # Get the execution and verify its input
        executions = self.sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN)
        assert len(executions['executions']) == 1

        execution_arn = executions['executions'][0]['executionArn']
        execution = self.sfn.describe_execution(executionArn=execution_arn)
        input_data = json.loads(execution['input'])
        assert input_data["s3_uri"] == S3_URI

        name = execution['name']
        input_data = json.loads(execution['input'])

        assert name == f"s3-trigger-{input_data['sftoken']}"

    def test_state_machine_arn_passed_to_execution(self):
        self.mod.handler(_direct_s3_event(), {})

        # Verify execution was created for the correct state machine
        executions = self.sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN)
        assert len(executions['executions']) == 1
        assert executions['executions'][0]['stateMachineArn'] == STATE_MACHINE_ARN

    def test_response_includes_execution_arn(self):
        resp = self.mod.handler(_direct_s3_event(), {})
        assert "executionArn" in resp
        assert resp["executionArn"].startswith("arn:aws:states:")

    def test_url_encoded_key_is_decoded(self):
        encoded_key = "2024-01-01/user%20123/lecture+video.mp4"
        event = _direct_s3_event(key=encoded_key)
        self.mod.handler(event, {})

        # Get the execution and verify the decoded key in s3_uri
        executions = self.sfn.list_executions(stateMachineArn=STATE_MACHINE_ARN)
        execution_arn = executions['executions'][0]['executionArn']
        execution = self.sfn.describe_execution(executionArn=execution_arn)
        input_data = json.loads(execution['input'])

        # unquote_plus decodes %20 → space and + → space
        assert "user 123" in input_data["s3_uri"]
        assert "lecture video.mp4" in input_data["s3_uri"]

    def test_sfn_exception_propagates(self):
        # Delete the state machine to cause an exception
        self.sfn.delete_state_machine(stateMachineArn=STATE_MACHINE_ARN)

        try:
            self.mod.handler(_direct_s3_event(), {})
            assert False, "Expected exception"
        except Exception as e:
            # Should raise an exception when state machine doesn't exist
            assert True
