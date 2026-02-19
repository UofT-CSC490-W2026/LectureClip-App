import boto3
import os
import json
import urllib.parse
import time

sfn_client = boto3.client("stepfunctions")

STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]
VIDEO_EXTENSIONS = [".mp4", ".mov"]


def _extract_s3_record(event):
    """Return the S3 sub-record from either a direct S3 event or an SNS-wrapped one."""
    record = event["Records"][0]
    if "Sns" in record:
        # SNS wraps the S3 notification as a JSON string in Sns.Message
        s3_message = json.loads(record["Sns"]["Message"])
        # S3 sends a test event when a notification is first configured
        if s3_message.get("Event") == "s3:TestEvent":
            return None
        return s3_message["Records"][0]["s3"]
    return record["s3"]


def handler(event, context):
    print(f"Event received: {json.dumps(event)}")

    try:
        s3_record = _extract_s3_record(event)
        if s3_record is None:
            print("S3 test event — skipping.")
            return {"statusCode": 200, "body": "Test event, skipped."}

        bucket = s3_record["bucket"]["name"]
        key = urllib.parse.unquote_plus(s3_record["object"]["key"])

        print(f"Object detected: s3://{bucket}/{key}")

        if not any(key.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
            print(f"Not a video file: {key} — skipping.")
            return {"statusCode": 200, "body": "Not a video file, skipped."}

        s3_uri = f"s3://{bucket}/{key}"
        filename = os.path.basename(key)
        file_prefix = filename[:6] if len(filename) >= 6 else filename
        timestamp = str(int(time.time()))
        machine_name = f"{timestamp}-{file_prefix}"

        response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"s3-trigger-{machine_name}",
            input=json.dumps({"s3_uri": s3_uri, "sftoken": machine_name}),
        )

        print(f"Workflow started: {response['executionArn']}")
        return {
            "statusCode": 200,
            "body": f"Workflow started for: {key}",
            "executionArn": response["executionArn"],
        }

    except Exception as e:
        print(f"Error processing event: {str(e)}")
        raise