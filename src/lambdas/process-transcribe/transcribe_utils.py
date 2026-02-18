import boto3

transcribe_client = boto3.client("transcribe")


def get_transcribe_result_data(event):
    """Extract job details from an EventBridge Transcribe Job State Change event."""
    job_name = event["detail"]["TranscriptionJobName"]
    job_status = event["detail"]["TranscriptionJobStatus"]

    response = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
    job_details = response["TranscriptionJob"]
    media_url = job_details["Media"]["MediaFileUri"]
    transcript_url = job_details["Transcript"]["TranscriptFileUri"]

    return job_name, job_status, job_details, media_url, transcript_url