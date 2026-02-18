#!/usr/bin/env bash
# invoke-local.sh — locally invoke LectureClip Lambda functions using SAM CLI
#
# Usage:
#   ./scripts/invoke-local.sh <function> [--event <file>] [--bucket <name>]
#
# Functions:
#   video-upload        POST /uploads       — returns a presigned PUT URL
#   multipart-init      POST /multipart/init  — creates multipart upload, returns presigned part URLs
#   multipart-complete  POST /multipart/complete — completes a multipart upload
#
# Prerequisites:
#   - AWS SAM CLI:   https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
#   - Docker running (sam local invoke uses a Lambda container image)
#   - AWS credentials configured (presigned URLs require real AWS creds + a real S3 bucket)
#
# Examples:
#   ./scripts/invoke-local.sh video-upload
#   ./scripts/invoke-local.sh multipart-init --bucket my-dev-bucket
#   ./scripts/invoke-local.sh multipart-complete --event events/multipart-complete.json

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── helpers ──────────────────────────────────────────────────────────────────

usage() {
  sed -n '/^# Usage:/,/^[^#]/{ /^#/{ s/^# \?//; p } }' "$0"
  exit 1
}

err() { echo "error: $*" >&2; exit 1; }

# ── defaults ─────────────────────────────────────────────────────────────────

BUCKET="${LECTURECLIP_BUCKET:-}"
EVENT_FILE=""
FUNCTION=""

# ── arg parsing ───────────────────────────────────────────────────────────────

[[ $# -eq 0 ]] && usage

FUNCTION="$1"; shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event)   EVENT_FILE="$2"; shift 2 ;;
    --bucket)  BUCKET="$2";     shift 2 ;;
    -h|--help) usage ;;
    *) err "unknown argument: $1" ;;
  esac
done

# ── resolve function name & default event ────────────────────────────────────

case "$FUNCTION" in
  video-upload)
    SAM_FUNCTION="VideoUploadFunction"
    DEFAULT_EVENT="events/video-upload.json"
    ;;
  multipart-init)
    SAM_FUNCTION="MultipartInitFunction"
    DEFAULT_EVENT="events/multipart-init.json"
    ;;
  multipart-complete)
    SAM_FUNCTION="MultipartCompleteFunction"
    DEFAULT_EVENT="events/multipart-complete.json"
    ;;
  *)
    err "unknown function '$FUNCTION'. Choose: video-upload | multipart-init | multipart-complete"
    ;;
esac

EVENT_FILE="${EVENT_FILE:-$DEFAULT_EVENT}"
[[ -f "$EVENT_FILE" ]] || err "event file not found: $EVENT_FILE"

# ── require a bucket ─────────────────────────────────────────────────────────

if [[ -z "$BUCKET" ]]; then
  # Try to detect from Terraform outputs if available
  if command -v terraform &>/dev/null && [[ -d terraform ]]; then
    BUCKET=$(terraform -chdir=terraform output -raw user_videos_bucket_id 2>/dev/null || true)
  fi
fi

if [[ -z "$BUCKET" ]]; then
  echo ""
  echo "  BUCKET_NAME is not set. Presigned URLs require a real S3 bucket."
  echo "  Set it via:"
  echo "    LECTURECLIP_BUCKET=my-bucket ./scripts/invoke-local.sh $FUNCTION"
  echo "    ./scripts/invoke-local.sh $FUNCTION --bucket my-bucket"
  echo ""
  echo "  Continuing with placeholder value 'lectureclip-local' — S3 calls will fail."
  echo ""
  BUCKET="lectureclip-local"
fi

# ── build env-vars override ──────────────────────────────────────────────────

ENV_JSON=$(mktemp /tmp/lectureclip-env-XXXX.json)
trap 'rm -f "$ENV_JSON"' EXIT

# SAM env-vars format: { "FunctionLogicalId": { "VAR": "value" } }
cat > "$ENV_JSON" <<EOF
{
  "$SAM_FUNCTION": {
    "BUCKET_NAME": "$BUCKET",
    "REGION": "${AWS_DEFAULT_REGION:-${AWS_REGION:-ca-central-1}}"
  }
}
EOF

# ── invoke ───────────────────────────────────────────────────────────────────

echo ""
echo "  function : $FUNCTION ($SAM_FUNCTION)"
echo "  event    : $EVENT_FILE"
echo "  bucket   : $BUCKET"
echo ""

sam local invoke "$SAM_FUNCTION" \
  --event "$EVENT_FILE" \
  --env-vars "$ENV_JSON" \
  --template template.yaml
