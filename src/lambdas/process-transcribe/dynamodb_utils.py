import json
import decimal
from datetime import datetime

import boto3

dynamodb = boto3.resource("dynamodb")


class _CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def _build_update_expression(to_update):
    attr_names = {}
    attr_values = {}
    expressions = []
    for i, (key, val) in enumerate(to_update.items()):
        name_token = f"#item{i}"
        value_token = f":val{i}"
        attr_names[name_token] = key
        attr_values[value_token] = val
        expressions.append(f"{name_token} = {value_token}")
    return attr_names, attr_values, f"SET {', '.join(expressions)}"


def update_item(table, key, update_obj):
    """Update a DynamoDB item and return its new attributes."""
    # Round-trip through JSON to normalise Decimal / datetime values
    normalised = json.loads(json.dumps(update_obj, cls=_CustomEncoder))
    attr_names, attr_values, update_expression = _build_update_expression(normalised)

    response = table.update_item(
        Key=key,
        UpdateExpression=update_expression,
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
        ReturnValues="ALL_NEW",
    )
    return response.get("Attributes", {})
