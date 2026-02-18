import os

import boto3

from transcribe_utils import get_transcribe_result_data
from dynamodb_utils import update_item
from step_function_utils import send_task_success, send_task_failure

dynamodb = boto3.resource("dynamodb")

TRANSCRIBE_TABLE_NAME = os.environ.get("TRANSCRIBE_TABLE")
transcribe_table = dynamodb.Table(TRANSCRIBE_TABLE_NAME)


def handler(event, context):
    """
    Triggered by EventBridge when an Amazon Transcribe job reaches a terminal state.
    Retrieves the Step Functions task token from DynamoDB and signals the workflow.
    """
    print(event)

    job_name, job_status, job_details, media_url, transcript_url = get_transcribe_result_data(event)
    print(job_details)

    to_update = {
        "status": job_status,
        "transcriptUrl": transcript_url,
        "mediaUrl": media_url,
    }
    updated_item = update_item(transcribe_table, {"TranscriptionJobName": job_name}, to_update)
    sftoken = updated_item.get("sftoken")

    print("Sending task signal to Step Functions...")
    if job_status == "COMPLETED":
        print(f"Job {job_name} completed successfully.")
        send_task_success(sftoken, to_update)
    else:
        print(f"Job {job_name} did not complete. Status: {job_status}")
        send_task_failure(
            sftoken,
            error_message=f"Transcription did not complete. Status: {job_status}",
        )