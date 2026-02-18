import boto3
import uuid
import os

transcribe_client = boto3.client("transcribe")

TRANSCRIBE_TABLE_NAME = os.environ.get("TRANSCRIBE_TABLE")
TRANSCRIPTS_BUCKET = os.environ.get("TRANSCRIPTS_BUCKET")

dynamodb = boto3.resource("dynamodb")
transcribe_table = dynamodb.Table(TRANSCRIBE_TABLE_NAME)


def _parse_s3_uri(s3_uri):
    """Return (bucket, prefix, filename, extension) from an s3:// URI."""
    without_scheme = s3_uri.split("s3://", 1)[1]
    parts = without_scheme.split("/")
    bucket = parts[0]
    prefix = "/".join(parts[1:-1])
    file = parts[-1]
    filename, extension = file.rsplit(".", 1)
    return bucket, prefix, filename, extension, file


def handler(event, context):
    print(event)
    s3_uri = event.get("s3_uri")
    # sftoken here is the Step Functions task token (injected by the state machine
    # as $$.Task.Token — not the execution name prefix from s3-trigger)
    sftoken = event.get("sftoken")
    job_name = str(uuid.uuid4())

    _bucket, prefix, _filename, _extension, file = _parse_s3_uri(s3_uri)

    output_key = f"{prefix}/{file}/transcribe.json" if prefix else f"{file}/transcribe.json"

    response = transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        IdentifyLanguage=True,
        OutputBucketName=TRANSCRIPTS_BUCKET,
        OutputKey=output_key,
        Media={"MediaFileUri": s3_uri},
        Settings={
            "ShowSpeakerLabels": True,
            "MaxSpeakerLabels": 10,
        },
    )

    job_status = response["TranscriptionJob"]["TranscriptionJobStatus"]

    transcribe_table.put_item(
        Item={
            "TranscriptionJobName": job_name,
            "status": job_status,
            "s3_uri": s3_uri,
            "sftoken": sftoken,
        }
    )

    return {"job_name": job_name}