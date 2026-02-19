#!/usr/bin/env bash
# deploy.sh — build and deploy LectureClip Lambdas directly to AWS
#
# SAM builds each function (installs requirements.txt), zips the output,
# and calls update-function-code with --zip-file. No S3 bucket required.
#
# Usage:
#   ./scripts/deploy.sh [--function <name>] [--region <region>]
#
# Functions:
#   video-upload        (default: all six)
#   multipart-init
#   multipart-complete
#   s3-trigger
#   start-transcribe
#   process-transcribe
#
# Prerequisites:
#   - AWS SAM CLI  (sam build requires Docker or --use-container)
#   - AWS CLI with credentials that have:
#       lambda:UpdateFunctionCode on lectureclip-* functions
#
# Examples:
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh --function video-upload
#   AWS_PROFILE=dev ./scripts/deploy.sh --function s3-trigger

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── helpers ───────────────────────────────────────────────────────────────────

log()  { echo "  [deploy] $*"; }
err()  { echo "  [error]  $*" >&2; exit 1; }
step() { echo ""; echo "▸ $*"; }

# ── defaults ──────────────────────────────────────────────────────────────────

REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-ca-central-1}}"
FILTER_FUNCTION=""   # empty = deploy all

# ── arg parsing ───────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --function) FILTER_FUNCTION="$2"; shift 2 ;;
    --region)   REGION="$2";          shift 2 ;;
    -h|--help)
      sed -n '/^# Usage:/,/^[^#]/{ /^#/{ s/^# \?//; p } }' "$0"
      exit 0
      ;;
    *) err "unknown argument: $1" ;;
  esac
done

# ── function registry ─────────────────────────────────────────────────────────
# Format: "short-name|SAM-logical-id|lambda-function-name"

ALL_FUNCTIONS=(
  "video-upload|VideoUploadFunction|lectureclip-video-upload"
  "multipart-init|MultipartInitFunction|lectureclip-multipart-init"
  "multipart-complete|MultipartCompleteFunction|lectureclip-multipart-complete"
  "s3-trigger|S3TriggerFunction|lectureclip-s3-trigger"
  "start-transcribe|StartTranscribeFunction|lectureclip-start-transcribe"
  "process-transcribe|ProcessTranscribeFunction|lectureclip-process-transcribe"
)

# ── filter to requested function ──────────────────────────────────────────────

FUNCTIONS_TO_DEPLOY=()
for entry in "${ALL_FUNCTIONS[@]}"; do
  short_name="${entry%%|*}"
  if [[ -z "$FILTER_FUNCTION" || "$FILTER_FUNCTION" == "$short_name" ]]; then
    FUNCTIONS_TO_DEPLOY+=("$entry")
  fi
done

[[ ${#FUNCTIONS_TO_DEPLOY[@]} -eq 0 ]] && err "unknown function '$FILTER_FUNCTION'. Choose: video-upload | multipart-init | multipart-complete | s3-trigger | start-transcribe | process-transcribe"

# ── summary ───────────────────────────────────────────────────────────────────

echo ""
echo "  region  : $REGION"
echo "  deploy  : $(names=(); for e in "${FUNCTIONS_TO_DEPLOY[@]}"; do names+=("${e%%|*}"); done; IFS=', '; echo "${names[*]}")"

# ── sam build ─────────────────────────────────────────────────────────────────

step "sam build"

if [[ -n "$FILTER_FUNCTION" ]]; then
  LOGICAL_ID="${FUNCTIONS_TO_DEPLOY[0]#*|}"
  LOGICAL_ID="${LOGICAL_ID%%|*}"
  sam build "$LOGICAL_ID" --template template.yaml --region "$REGION"
else
  sam build --template template.yaml --region "$REGION"
fi

BUILD_DIR=".aws-sam/build"

# ── package & deploy each function ───────────────────────────────────────────

for entry in "${FUNCTIONS_TO_DEPLOY[@]}"; do
  IFS='|' read -r short_name logical_id lambda_name <<< "$entry"

  step "$short_name"

  build_artifact_dir="$BUILD_DIR/$logical_id"
  [[ -d "$build_artifact_dir" ]] || err "build output not found: $build_artifact_dir"

  zip_file="/tmp/${short_name}-$(date +%s).zip"

  log "zipping $build_artifact_dir → $zip_file"
  (cd "$build_artifact_dir" && zip -qr "$zip_file" .)

  log "updating function code: $lambda_name"
  aws lambda update-function-code \
    --function-name "$lambda_name" \
    --zip-file "fileb://$zip_file" \
    --region "$REGION" \
    --output text \
    --query 'FunctionName' \
    > /dev/null

  rm -f "$zip_file"

  log "waiting for update to complete..."
  aws lambda wait function-updated \
    --function-name "$lambda_name" \
    --region "$REGION"

  log "done ✓"
done

echo ""
echo "  Deploy complete."
echo ""