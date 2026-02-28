# LectureClip - Application

Serverless AWS backend for uploading lecture videos directly to S3 and transcribing them with Amazon Transcribe.

## Architecture

### Video Upload

```
Client
  │
  ├─ file ≤ 100 MB ──► POST /upload            ──► VideoUploadFunction
  │                         returns presigned PUT URL
  │
  └─ file > 100 MB ──► POST /multipart/init    ──► MultipartInitFunction
                            returns uploadId + presigned part URLs
                        POST /multipart/complete ──► MultipartCompleteFunction
                            finalizes upload with ETags
```

The upload Lambdas are Python 3.13, read `BUCKET_NAME` and `REGION` from environment variables, and respond with `Access-Control-Allow-Origin: *` headers.

**S3 key format:** `{ISO-timestamp}/{userId}/{filename}`

### Audio Transcription Pipeline

Once a video lands in S3, an SNS notification triggers the transcription workflow:

```
S3 Event (via SNS)
  │
  └──► S3TriggerFunction          filters .mp4/.mov files, starts Step Functions execution
         │
         └──► Step Functions State Machine
                │
                └──► StartTranscribeFunction   starts Transcribe job; stores task token in DynamoDB
                           │
                           └──► Amazon Transcribe (async)
                                  │
                                  └──► EventBridge (job completion)
                                         │
                                         └──► ProcessTranscribeFunction  signals Step Functions success/failure
```

| Lambda | Trigger | Key env vars |
|--------|---------|-------------|
| `s3-trigger` | SNS-wrapped S3 `ObjectCreated` event | `STATE_MACHINE_ARN` |
| `start-transcribe` | Step Functions (`waitForTaskToken`) | `TRANSCRIBE_TABLE`, `TRANSCRIPTS_BUCKET` |
| `process-transcribe` | EventBridge (Transcribe job state change) | `TRANSCRIBE_TABLE` |

## Repository Structure

```
LectureClip-App/
├── src/
│   └── lambdas/
│       ├── video-upload/
│       │   └── index.py                  # POST /upload — presigned PUT URL for files ≤ 100 MB
│       ├── multipart-init/
│       │   └── index.py                  # POST /multipart/init — create multipart upload, return part URLs
│       ├── multipart-complete/
│       │   └── index.py                  # POST /multipart/complete — finalize multipart upload
│       ├── s3-trigger/
│       │   └── index.py                  # SNS/S3 trigger — filters video files, starts Step Functions
│       ├── start-transcribe/
│       │   └── index.py                  # Step Functions task — starts Transcribe job, stores token in DynamoDB
│       └── process-transcribe/
│           ├── index.py                  # EventBridge trigger — signals Step Functions on Transcribe completion
│           ├── dynamodb_utils.py         # DynamoDB helpers
│           ├── step_function_utils.py    # Step Functions signal helpers
│           └── transcribe_utils.py      # Transcribe result parsing helpers
├── tests/
│   ├── conftest.py                # Shared fixtures and Lambda loader
│   ├── test_video_upload.py       # Unit tests for POST /upload
│   ├── test_multipart_init.py     # Unit tests for POST /multipart/init
│   ├── test_multipart_complete.py # Unit tests for POST /multipart/complete
│   ├── test_upload_flow.py        # End-to-end flow tests mirroring upload_video.py
│   └── requirements.txt           # Test dependencies (pytest, boto3)
├── events/
│   ├── video-upload.json          # Sample event for local SAM testing
│   ├── multipart-init.json
│   └── multipart-complete.json
├── scripts/
│   ├── invoke-local.sh            # Run a Lambda locally with SAM CLI
│   └── deploy.sh                  # Build and deploy Lambdas to AWS
├── .github/
│   └── workflows/
│       └── deploy-lambda.yml      # CI/CD — deploys on push to main when src/ changes
├── pytest.ini                     # Points pytest at tests/
└── template.yaml                  # SAM template (local dev + CI builds)
```

## Prerequisites

| Tool | Purpose |
|------|---------|
| AWS SAM CLI | `sam build` and `sam local invoke` |
| Docker | Required by `sam local invoke` for Lambda containers |
| AWS CLI | Credentials for S3 presigned URL generation and deployment |
| Python 3.13 | Lambda runtime and CLI client |

## Local Development

### Invoke a function locally

```bash
# All three functions — uses the default event file in events/
LECTURECLIP_BUCKET=my-dev-bucket ./scripts/invoke-local.sh video-upload
LECTURECLIP_BUCKET=my-dev-bucket ./scripts/invoke-local.sh multipart-init
LECTURECLIP_BUCKET=my-dev-bucket ./scripts/invoke-local.sh multipart-complete

# Override the event payload
./scripts/invoke-local.sh video-upload --event events/video-upload.json

# Override the bucket inline
./scripts/invoke-local.sh multipart-init --bucket my-other-bucket
```

The script:
1. Resolves the SAM logical function name from the short name (e.g. `video-upload` → `VideoUploadFunction`)
2. Writes a temporary env-vars JSON with `BUCKET_NAME` and `REGION`
3. Runs `sam local invoke` against `template.yaml`

### Build

```bash
# Build all functions
sam build --template template.yaml

# Build a single function
sam build VideoUploadFunction --template template.yaml
```

Build output lands in `.aws-sam/build/`.

### Event payloads

Sample payloads live in `events/`. Edit them to test different inputs:

```json
// events/video-upload.json
{
  "httpMethod": "POST",
  "body": "{\"filename\": \"lecture.mp4\", \"userId\": \"user-123\", \"contentType\": \"video/mp4\"}"
}

// events/multipart-init.json — fileSize in bytes
{
  "httpMethod": "POST",
  "body": "{\"filename\": \"large-lecture.mp4\", \"userId\": \"user-123\", \"contentType\": \"video/mp4\", \"fileSize\": 524288000}"
}

// events/multipart-complete.json — fill in real uploadId and ETags from a prior init call
{
  "httpMethod": "POST",
  "body": "{\"fileKey\": \"...\", \"uploadId\": \"REPLACE\", \"parts\": [{\"PartNumber\": 1, \"ETag\": \"REPLACE\"}]}"
}
```

Files ≤ 100 MB → direct upload via `/upload`.
Files > 100 MB → multipart upload via `/multipart/init` + `/multipart/complete`, uploading 100 MB parts in sequence.

Supported formats: `mp4`, `mov`, `avi`, `webm`, `mpeg`, `mkv`

## Tests

Unit tests cover each Lambda handler and an end-to-end flow that mirrors `upload_video.py`. No AWS credentials or network access required — boto3 is mocked with `unittest.mock`.

### Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r tests/requirements.txt
```

### Run

```bash
# All tests
pytest

# A specific file
pytest tests/test_upload_flow.py

# Verbose output
pytest -v
```

### Test layout

| File | What it tests |
|------|--------------|
| `test_video_upload.py` | `POST /upload` — presigned URL params, content-type validation, CORS |
| `test_multipart_init.py` | `POST /multipart/init` — part count math, sequential part numbers, validation |
| `test_multipart_complete.py` | `POST /multipart/complete` — S3 call params, missing field rejection |
| `test_upload_flow.py` | Full direct and multipart flows calling handlers in sequence, as `upload_video.py` does |

### Writing a new test

Each test file loads its Lambda handler once at module level using `load_lambda()` from `conftest.py`, then patches the module-level `s3_client` per test:

```python
from conftest import load_lambda, make_event, parse_body
from unittest.mock import patch

mod = load_lambda("my-new-function")

def test_something(mock_s3):
    mock_s3.some_method.return_value = {"Key": "value"}
    with patch.object(mod, "s3_client", mock_s3):
        resp = mod.handler(make_event({"field": "value"}), {})
    assert resp["statusCode"] == 200
```

## Adding a New Lambda

1. **Create the function directory and handler:**

   ```bash
   mkdir src/lambdas/my-new-function
   # create src/lambdas/my-new-function/index.py with a handler(event, context) function
   ```

2. **Register it in `template.yaml`:**

   ```yaml
   MyNewFunction:
     Type: AWS::Serverless::Function
     Properties:
       FunctionName: !Sub "lectureclip-${Environment}-my-new-function"
       Handler: index.handler
       CodeUri: src/lambdas/my-new-function/
   ```

   The `Globals` block already sets `Runtime: python3.13`, `Timeout: 30`, and injects `BUCKET_NAME` / `REGION` as environment variables — no need to repeat those. The `Environment` SAM parameter is set to `dev` or `prod` at build time.

3. **Add a sample event payload:**

   ```bash
   # create events/my-new-function.json
   ```

4. **Register it in `scripts/deploy.sh`** by adding an entry to `ALL_FUNCTIONS`:

   ```bash
   "my-new-function|MyNewFunction"
   ```

   The Lambda function name is derived automatically as `lectureclip-{env}-my-new-function` at deploy time.

5. **Register it in `scripts/invoke-local.sh`** by adding a case in the function resolver:

   ```bash
   my-new-function)
     SAM_FUNCTION="MyNewFunction"
     DEFAULT_EVENT="events/my-new-function.json"
     ;;
   ```

6. **Add a deploy job to `.github/workflows/deploy-lambda.yml`** following the pattern of the existing jobs: add `needs: resolve-env`, use `needs.resolve-env.outputs.role` for the IAM role, and set the function name to `lectureclip-${{ needs.resolve-env.outputs.env_name }}-my-new-function`.

7. **Add tests in `tests/`** — create `tests/test_my_new_function.py` following the pattern of the existing test files: load the handler with `load_lambda("my-new-function")`, patch `s3_client`, and call `mod.handler(make_event({...}), {})`.

8. **Test locally:**

   ```bash
   LECTURECLIP_BUCKET=my-bucket ./scripts/invoke-local.sh my-new-function
   ```

## Deployment
### Authenticate with SSO
If using AWS SSO, run:

```bash
aws sso login --profile <your-profile-name>
export AWS_PROFILE=<your-profile-name>
```

### Automated (CI/CD)

Pushing to `main` or `develop` with changes under `src/lambdas/` triggers `.github/workflows/deploy-lambda.yml`. A `resolve-env` job maps the branch to the target environment (`develop` → dev, `main` → prod), then each Lambda is built and deployed in a separate parallel job using the appropriate role and the `lectureclip-{env}-{function}` naming convention.

Required GitHub Actions variables (set under Settings → Variables):

| Variable | Description |
|----------|-------------|
| `AWS_REGION` | e.g. `ca-central-1` |
| `AWS_ROLE_TO_ASSUME_DEV` | IAM role ARN for OIDC federation (dev environment) |
| `AWS_ROLE_TO_ASSUME_PROD` | IAM role ARN for OIDC federation (prod environment) |

### Manual

```bash
# Deploy all functions to dev (default)
./scripts/deploy.sh

# Deploy all functions to prod
./scripts/deploy.sh --env prod

# Deploy a single function
./scripts/deploy.sh --env dev --function video-upload

# Override region
./scripts/deploy.sh --env prod --region us-east-1

# Use a specific AWS profile
AWS_PROFILE=prod ./scripts/deploy.sh --env prod --function multipart-init
```

The deploy script:
1. Runs `sam build --parameter-overrides Environment={env}` (installs any `requirements.txt` into the build artifact)
2. Zips the build output
3. Calls `aws lambda update-function-code --zip-file` directly to `lectureclip-{env}-{function}` and waits for the update to propagate
