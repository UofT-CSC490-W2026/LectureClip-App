"""
Shared test infrastructure.

conftest.py is loaded by pytest before any test module, so the os.environ
assignments at the top execute before any Lambda module is imported — which
matters because each Lambda reads BUCKET_NAME / REGION at import time.
"""

import os
import sys

# Must be set before Lambda modules are imported.
os.environ.setdefault("BUCKET_NAME", "test-bucket")
os.environ.setdefault("REGION", "us-east-1")
# boto3 reads AWS_DEFAULT_REGION, not REGION.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

# process-transcribe imports sibling modules (transcribe_utils, etc.) by bare
# name, so its directory must be on sys.path before load_lambda runs.
_PROCESS_TRANSCRIBE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "lambdas", "process-transcribe",
)
if _PROCESS_TRANSCRIBE_DIR not in sys.path:
    sys.path.insert(0, _PROCESS_TRANSCRIBE_DIR)
os.environ.setdefault("STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:TestMachine")
os.environ.setdefault("TRANSCRIBE_TABLE", "test-transcribe-table")
os.environ.setdefault("TRANSCRIPTS_BUCKET", "test-transcripts-bucket")

import importlib.util
import json

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_BUCKET = os.environ["BUCKET_NAME"]
TEST_USER_ID = "user-test-123"


def load_lambda(name: str):
    """
    Load a Lambda handler by its short directory name (e.g. 'video-upload').

    Each call returns a fresh module object, so test files that both load the
    same Lambda get independent references — patching one won't affect another.
    """
    path = os.path.join(REPO_ROOT, "src", "lambdas", name, "index.py")
    module_name = f"lambda_{name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_event(body: dict, method: str = "POST") -> dict:
    """Build a minimal API Gateway v1 proxy event."""
    return {
        "httpMethod": method,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def parse_body(response: dict) -> dict:
    """Decode the JSON body string from a Lambda response dict."""
    return json.loads(response["body"])
