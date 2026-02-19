# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LectureClip is a serverless video processing backend on AWS. It handles video uploads via presigned S3 URLs and automatically transcribes uploaded videos using Amazon Transcribe, orchestrated with AWS Step Functions.

## Architecture

### Upload lambdas (`src/lambdas/`)

1. **`video-upload/`** — `POST /upload`: For files ≤100 MB. Returns a single presigned `PUT` URL for direct S3 upload.
2. **`multipart-init/`** — `POST /multipart/init`: For files >100 MB. Creates an S3 multipart upload and returns presigned URLs for each 100 MB part.
3. **`multipart-complete/`** — `POST /multipart/complete`: Finalizes a multipart upload by calling `complete_multipart_upload` with the ETags from each part.

### Transcription pipeline (`src/lambdas/`)

Triggered automatically when a video lands in S3, orchestrated by a Step Functions state machine:

4. **`s3-trigger/`** — Receives S3 (or SNS-wrapped S3) events, filters for video files (`.mp4`, `.mov`), and starts a Step Functions execution.
5. **`start-transcribe/`** — Step Functions task: starts an Amazon Transcribe job with speaker labels and language identification, stores job metadata in DynamoDB.
6. **`process-transcribe/`** — Triggered by EventBridge when a Transcribe job reaches a terminal state. Reads the task token from DynamoDB and signals Step Functions with success or failure.
   - `transcribe_utils.py` — fetches job details from the Transcribe API.
   - `dynamodb_utils.py` — generic `update_item` helper with expression builder.
   - `step_function_utils.py` — `send_task_success` / `send_task_failure` wrappers.

### Other

`upload_video.py` is a CLI client that calls the upload endpoints through API Gateway, automatically choosing direct vs. multipart based on whether the file exceeds 100 MB. It uses the `requests` library (see `requirements.txt`).

### Environment variables

| Variable | Used by |
|---|---|
| `BUCKET_NAME` | upload lambdas |
| `REGION` | upload lambdas |
| `STATE_MACHINE_ARN` | `s3-trigger` |
| `TRANSCRIBE_TABLE` | `start-transcribe`, `process-transcribe` |
| `TRANSCRIPTS_BUCKET` | `start-transcribe` |

S3 key format: `{ISO-timestamp}/{userId}/{filename}`

## Testing

```bash
python -m pytest          # run all tests
python -m pytest -v       # verbose
```

Tests live in `tests/`. `conftest.py` sets all required environment variables (including `AWS_DEFAULT_REGION` for boto3) and adds `src/lambdas/process-transcribe/` to `sys.path` so its sibling modules are importable. Lambda modules are loaded via `load_lambda("function-dir-name")` which uses `importlib` to handle the hyphenated directory names.

## Local Development

Prerequisites: AWS SAM CLI, Docker (for `sam local invoke`), AWS credentials with access to a real S3 bucket (presigned URLs require real credentials).

```bash
# Invoke a function locally against a real S3 bucket
LECTURECLIP_BUCKET=my-bucket ./scripts/invoke-local.sh video-upload
LECTURECLIP_BUCKET=my-bucket ./scripts/invoke-local.sh multipart-init
LECTURECLIP_BUCKET=my-bucket ./scripts/invoke-local.sh multipart-complete

# Override the event payload
./scripts/invoke-local.sh video-upload --event events/video-upload.json

# Build all functions
sam build --template template.yaml

# Build a single function
sam build VideoUploadFunction --template template.yaml
```

Sample event payloads live in `events/`. There is currently no `events/multipart-complete.json`; it must be created manually with `fileKey`, `uploadId`, and `parts` fields.

## Deployment

CI/CD deploys automatically on push to `main` when files under `lambdas/` change (`.github/workflows/deploy-lambda.yml`). Each Lambda is deployed independently. Required GitHub Actions variables: `AWS_REGION`, `AWS_ROLE_TO_ASSUME`, `AWS_ACCOUNT_ID`.

Manual deployment:
```bash
# Deploy all functions
./scripts/deploy.sh

# Deploy a single function
./scripts/deploy.sh --function video-upload

# Deploy to a specific bucket/region
./scripts/deploy.sh --bucket lectureclip-lambda-artifacts-123456789 --region us-east-1
```

The deploy script resolves the artifacts bucket as `lectureclip-lambda-artifacts-{AWS_ACCOUNT_ID}`.