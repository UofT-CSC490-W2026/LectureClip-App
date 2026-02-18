import json
import decimal

import boto3

sfn_client = boto3.client("stepfunctions")


class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        return super().default(obj)


def send_task_success(token, output):
    return sfn_client.send_task_success(
        taskToken=token,
        output=json.dumps(output, cls=_DecimalEncoder),
    )


def send_task_failure(token, error_code="TaskFailure", error_message="Task execution failed"):
    return sfn_client.send_task_failure(
        taskToken=token,
        error=error_code,
        cause=error_message,
    )