# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LectureClip is a serverless video upload backend on AWS. It provides S3 presigned URL generation via Python Lambda functions, allowing clients to upload video files directly to S3 without routing data through Lambda.

## Architecture

Three Lambda functions handle the video upload lifecycle:

1. **`lambdas/video-upload/`** — `POST /upload`: For files ≤100 MB. Returns a single presigned `PUT` URL for direct S3 upload.
2. **`lambdas/multipart-init/`** — `POST /multipart/init`: For files >100 MB. Creates an S3 multipart upload and returns presigned URLs for each 100 MB part.
3. **`lambdas/multipart-complete/`** — `POST /multipart/complete`: Finalizes a multipart upload by calling `complete_multipart_upload` with the ETags collected from each part.

`upload_video.py` is a CLI client that calls these endpoints through API Gateway, automatically choosing direct vs. multipart based on whether the file exceeds 100 MB. It uses the `requests` library (see `requirements.txt`).

All lambdas read `BUCKET_NAME` and `REGION` from environment variables and respond with CORS headers supporting `*` origin.

S3 key format: `{ISO-timestamp}/{userId}/{filename}`

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