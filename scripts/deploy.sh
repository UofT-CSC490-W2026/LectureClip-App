#!/usr/bin/env bash
# deploy.sh — build and deploy LectureClip Lambdas to AWS using ls
#
# SAM builds each function (installs requirements.txt), zips the output, uploads
# to the Lambda artifacts S3 bucket, then calls update-function-code on the
# Terraform-managed Lambda functions.
#
# Usage:
#   ./scripts/deploy.sh [--function <name>] [--bucket <name>] [--region <region>]
#
# Functions:
#   video-upload        (default: all three)
#   multipart-init
#   multipart-complete
#
# Prerequisites:
#   - AWS SAM CLI  (sam build requires Docker or --use-container)
#   - AWS CLI with credentials that have:
#       s3:PutObject on the artifacts bucket
#       lambda:UpdateFunctionCode on lectureclip-* functions
#
# Examples:
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh --function video-upload
#   ./scripts/deploy.sh --bucket lectureclip-lambda-artifacts-123456789012
#   AWS_PROFILE=dev ./scripts/deploy.sh --function multipart-init

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── helpers ───────────────────────────────────────────────────────────────────

log()  { echo "  [deploy] $*"; }
err()  { echo "  [error]  $*" >&2; exit 1; }
step() { echo ""; echo "▸ $*"; }

# ── defaults ──────────────────────────────────────────────────────────────────

REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-ca-central-1}}"
BUCKET=""
FILTER_FUNCTION=""   # empty = deploy all

# ── arg parsing ───────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --function) FILTER_FUNCTION="$2"; shift 2 ;;
    --bucket)   BUCKET="$2";          shift 2 ;;
    --region)   REGION="$2";          shift 2 ;;
    -h|--help)
      sed -n '/^# Usage:/,/^[^#]/{ /^#/{ s/^# \?//; p } }' "$0"
      exit 0
      ;;
    *) err "unknown argument: $1" ;;
  esac
done

# ── resolve artifacts bucket ──────────────────────────────────────────────────

if [[ -z "$BUCKET" ]]; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)
  [[ -n "$ACCOUNT_ID" ]] && BUCKET="lectureclip-lambda-artifacts-${ACCOUNT_ID}"
fi

[[ -z "$BUCKET" ]] && err "could not determine artifacts bucket. Pass --bucket <name> or ensure AWS credentials are configured."

# ── function registry ─────────────────────────────────────────────────────────
# Format: "short-name|SAM-logical-id|lambda-function-name|s3-key"

ALL_FUNCTIONS=(
  "video-upload|VideoUploadFunction|lectureclip-video-upload|lambdas/video-upload/video_upload.zip"
  "multipart-init|MultipartInitFunction|lectureclip-multipart-init|lambdas/multipart-init/multipart_init.zip"
  "multipart-complete|MultipartCompleteFunction|lectureclip-multipart-complete|lambdas/multipart-complete/multipart_complete.zip"
)

# ── filter to requested function ──────────────────────────────────────────────

FUNCTIONS_TO_DEPLOY=()
for entry in "${ALL_FUNCTIONS[@]}"; do
  short_name="${entry%%|*}"
  if [[ -z "$FILTER_FUNCTION" || "$FILTER_FUNCTION" == "$short_name" ]]; then
    FUNCTIONS_TO_DEPLOY+=("$entry")
  fi
done

[[ ${#FUNCTIONS_TO_DEPLOY[@]} -eq 0 ]] && err "unknown function '$FILTER_FUNCTION'. Choose: video-upload | multipart-init | multipart-complete"

# ── summary ───────────────────────────────────────────────────────────────────

echo ""
echo "  region  : $REGION"
echo "  bucket  : $BUCKET"
echo "  deploy  : $(IFS=', '; names=(); for e in "${FUNCTIONS_TO_DEPLOY[@]}"; do names+=("${e%%|*}"); done; echo "${names[*]}")"

# ── sam build ─────────────────────────────────────────────────────────────────
# Builds only the functions we need (skips unchanged ones if incremental).
# Installs requirements.txt into the build artifact directory.

step "sam build"

if [[ -n "$FILTER_FUNCTION" ]]; then
  # Build only the requested logical function
  LOGICAL_ID="${FUNCTIONS_TO_DEPLOY[0]#*|}"
  LOGICAL_ID="${LOGICAL_ID%%|*}"
  sam build "$LOGICAL_ID" --template template.yaml --region "$REGION"
else
  sam build --template template.yaml --region "$REGION"
fi

BUILD_DIR=".aws-sam/build"

# ── package & deploy each function ───────────────────────────────────────────

for entry in "${FUNCTIONS_TO_DEPLOY[@]}"; do
  IFS='|' read -r short_name logical_id lambda_name s3_key <<< "$entry"

  step "$short_name"

  build_artifact_dir="$BUILD_DIR/$logical_id"
  [[ -d "$build_artifact_dir" ]] || err "build output not found: $build_artifact_dir"

  zip_file="/tmp/${short_name}-$(date +%s).zip"

  log "zipping $build_artifact_dir → $zip_file"
  (cd "$build_artifact_dir" && zip -qr "$zip_file" .)

  log "uploading to s3://$BUCKET/$s3_key"
  aws s3 cp "$zip_file" "s3://$BUCKET/$s3_key" --region "$REGION"
  rm -f "$zip_file"

  log "updating function code: $lambda_name"
  aws lambda update-function-code \
    --function-name "$lambda_name" \
    --s3-bucket "$BUCKET" \
    --s3-key "$s3_key" \
    --region "$REGION" \
    --output text \
    --query 'FunctionName' \
    > /dev/null

  log "waiting for update to complete..."
  aws lambda wait function-updated \
    --function-name "$lambda_name" \
    --region "$REGION"

  log "done ✓"
done

echo ""
echo "  Deploy complete."
echo ""
