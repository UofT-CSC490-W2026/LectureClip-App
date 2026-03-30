#!/usr/bin/env bash
# deploy.sh — build and deploy LectureClip Lambdas directly to AWS
#
# SAM builds each function (installs requirements.txt), zips the output,
# and calls update-function-code with --zip-file. No S3 bucket required.
#
# After deploying db-migrate, the script automatically invokes it
# synchronously to apply any pending schema changes to Aurora.
#
# Usage:
#   ./scripts/deploy.sh [--env <dev|eval|prod>] [--function <name>] [--region <region>]
#
# Environments:
#   dev   (default) — targets lectureclip-dev-* Lambda functions
#   eval            — targets lectureclip-eval-* Lambda functions
#   prod            — targets lectureclip-prod-* Lambda functions
#
# Functions:
#   video-upload        (default: all)
#   multipart-init
#   multipart-complete
#   s3-trigger
#   start-transcribe
#   process-transcribe
#   process-results
#   db-migrate
#   query-segments
#   query-segments-info
#
# Prerequisites:
#   - AWS SAM CLI  (sam build requires Docker or --use-container)
#   - AWS CLI with credentials that have:
#       lambda:UpdateFunctionCode on lectureclip-{env}-* functions
#       lambda:InvokeFunction     on lectureclip-{env}-db-migrate
#
# Examples:
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh --env prod
#   ./scripts/deploy.sh --env eval --function query-segments
#   ./scripts/deploy.sh --env dev --function video-upload
#   AWS_PROFILE=prod ./scripts/deploy.sh --env prod --function s3-trigger

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── helpers ───────────────────────────────────────────────────────────────────

log()  { echo "  [deploy] $*"; }
err()  { echo "  [error]  $*" >&2; exit 1; }
step() { echo ""; echo "▸ $*"; }

# ── defaults ──────────────────────────────────────────────────────────────────

REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-ca-central-1}}"
ENV="dev"                  # dev, eval, or prod
FILTER_FUNCTION=""         # empty = deploy all
EMBEDDING_MODEL_ID=""      # overrides EmbeddingModelId SAM parameter
MODAL_EMBEDDING_URL=""     # overrides ModalEmbeddingUrl SAM parameter

# ── arg parsing ───────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)                  ENV="$2";                  shift 2 ;;
    --function)             FILTER_FUNCTION="$2";      shift 2 ;;
    --region)               REGION="$2";               shift 2 ;;
    --embedding-model-id)   EMBEDDING_MODEL_ID="$2";   shift 2 ;;
    --modal-embedding-url)  MODAL_EMBEDDING_URL="$2";  shift 2 ;;
    -h|--help)
      sed -n '/^# Usage:/,/^[^#]/{ /^#/{ s/^# \?//; p } }' "$0"
      exit 0
      ;;
    *) err "unknown argument: $1" ;;
  esac
done

[[ "$ENV" == "dev" || "$ENV" == "eval" || "$ENV" == "prod" ]] || err "--env must be 'dev', 'eval', or 'prod' (got '$ENV')"

# ── function registry ─────────────────────────────────────────────────────────
# Format: "short-name|SAM-logical-id"
# Lambda function name is derived at deploy time: lectureclip-{env}-{short-name}

ALL_FUNCTIONS=(
  "video-upload|VideoUploadFunction"
  "multipart-init|MultipartInitFunction"
  "multipart-complete|MultipartCompleteFunction"
  "s3-trigger|S3TriggerFunction"
  "start-transcribe|StartTranscribeFunction"
  "process-transcribe|ProcessTranscribeFunction"
  "process-results|ProcessResultsFunction"
  "db-migrate|DbMigrateFunction"
  "query-segments|QuerySegmentsFunction"
  "query-segments-info|QuerySegmentsInfoFunction"
  "chat|ChatFunction"
  "register-user|RegisterUserFunction"
  "list-lectures|ListLecturesFunction"
)

# ── filter to requested function ──────────────────────────────────────────────

FUNCTIONS_TO_DEPLOY=()
for entry in "${ALL_FUNCTIONS[@]}"; do
  short_name="${entry%%|*}"
  if [[ -z "$FILTER_FUNCTION" || "$FILTER_FUNCTION" == "$short_name" ]]; then
    FUNCTIONS_TO_DEPLOY+=("$entry")
  fi
done

[[ ${#FUNCTIONS_TO_DEPLOY[@]} -eq 0 ]] && err "unknown function '$FILTER_FUNCTION'. Choose: video-upload | multipart-init | multipart-complete | s3-trigger | start-transcribe | process-transcribe | process-results | db-migrate | query-segments | query-segments-info | chat | register-user | list-lectures"

# ── summary ───────────────────────────────────────────────────────────────────

echo ""
echo "  env     : $ENV"
echo "  region  : $REGION"
echo "  deploy  : $(names=(); for e in "${FUNCTIONS_TO_DEPLOY[@]}"; do names+=("${e%%|*}"); done; IFS=', '; echo "${names[*]}")"

# ── sam build ─────────────────────────────────────────────────────────────────

step "sam build"

SAM_PARAM_OVERRIDES="Environment=$ENV"

if [[ -n "$FILTER_FUNCTION" ]]; then
  LOGICAL_ID="${FUNCTIONS_TO_DEPLOY[0]#*|}"
  sam build "$LOGICAL_ID" --template template.yaml --region "$REGION" \
    --parameter-overrides "$SAM_PARAM_OVERRIDES"
else
  sam build --template template.yaml --region "$REGION" \
    --parameter-overrides "$SAM_PARAM_OVERRIDES"
fi

BUILD_DIR=".aws-sam/build"

# ── package & deploy each function ───────────────────────────────────────────

for entry in "${FUNCTIONS_TO_DEPLOY[@]}"; do
  IFS='|' read -r short_name logical_id <<< "$entry"
  lambda_name="lectureclip-${ENV}-${short_name}"

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

# ── update embedding env vars ────────────────────────────────────────────────
# Only runs when --embedding-model-id or --modal-embedding-url is passed.
# Merges the new values into each lambda's existing env vars (preserving the
# Terraform-managed AURORA_* vars) via update-function-configuration.

EMBEDDING_LAMBDAS=("process-results" "query-segments" "query-segments-info" "chat")

update_embedding_env() {
  local short_name="$1"
  local lambda_name="lectureclip-${ENV}-${short_name}"

  log "fetching current env vars: $lambda_name"
  local current_vars
  current_vars=$(aws lambda get-function-configuration \
    --function-name "$lambda_name" \
    --region "$REGION" \
    --query 'Environment.Variables' \
    --output json 2>/dev/null || echo '{}')

  local cfg_file
  cfg_file=$(mktemp --suffix=.json)

  python3 - "$lambda_name" "$current_vars" "$EMBEDDING_MODEL_ID" "$MODAL_EMBEDDING_URL" \
    > "$cfg_file" << 'PYEOF'
import json, sys
name, vars_json, model_id, modal_url = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
env = json.loads(vars_json)
if model_id: env['EMBEDDING_MODEL_ID'] = model_id
if modal_url: env['MODAL_EMBEDDING_URL'] = modal_url
print(json.dumps({"FunctionName": name, "Environment": {"Variables": env}}))
PYEOF

  log "updating env vars: $lambda_name"
  aws lambda update-function-configuration \
    --cli-input-json "file://$cfg_file" \
    --region "$REGION" \
    --output text \
    --query 'FunctionName' > /dev/null

  rm -f "$cfg_file"

  log "waiting for update to complete..."
  aws lambda wait function-updated \
    --function-name "$lambda_name" \
    --region "$REGION"

  log "done ✓"
}

if [[ -n "$EMBEDDING_MODEL_ID" || -n "$MODAL_EMBEDDING_URL" ]]; then
  step "updating embedding env vars"
  for short_name in "${EMBEDDING_LAMBDAS[@]}"; do
    update_embedding_env "$short_name"
  done
fi

# ── run db-migrate if it was deployed ────────────────────────────────────────
# db-migrate is idempotent (all DDL uses IF NOT EXISTS) so invoking it on
# every deploy is safe and ensures the schema is always up to date.

DB_MIGRATE_DEPLOYED=false
for entry in "${FUNCTIONS_TO_DEPLOY[@]}"; do
  [[ "${entry%%|*}" == "db-migrate" ]] && DB_MIGRATE_DEPLOYED=true && break
done

if [[ "$DB_MIGRATE_DEPLOYED" == "true" ]]; then
  step "invoking db-migrate"
  RESPONSE_FILE="/tmp/db-migrate-response-$(date +%s).json"
  INVOKE_META=$(aws lambda invoke \
    --function-name "lectureclip-${ENV}-db-migrate" \
    --invocation-type RequestResponse \
    --region "$REGION" \
    --output json \
    --payload '{}' \
    "$RESPONSE_FILE" 2>&1)

  if echo "$INVOKE_META" | grep -q '"FunctionError"'; then
    log "db-migrate response:"
    cat "$RESPONSE_FILE" >&2
    rm -f "$RESPONSE_FILE"
    err "db-migrate Lambda reported a function error — schema migration failed"
  fi

  log "db-migrate response: $(cat "$RESPONSE_FILE")"
  rm -f "$RESPONSE_FILE"
  log "done ✓"
fi

echo ""
echo "  Deploy complete."
echo ""