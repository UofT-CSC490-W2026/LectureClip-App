import json
import boto3
import os
from datetime import datetime

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ['BUCKET_NAME']
REGION = os.environ['REGION']

ALLOWED_TYPES = ['video/mp4', 'video/mov']
PRESIGNED_URL_EXPIRY = 300  # 5 minutes


def handler(event, context):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'POST,OPTIONS',
    }

    try:
        # Handle CORS preflight
        http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', '')
        if http_method == 'OPTIONS':
            return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': 'CORS preflight successful'})}

        # Parse body
        raw_body = event.get('body') or event
        body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body

        filename_path = body.get('filename', 'video.mp4')
        user_id = body.get('userId', 'anonymous')
        content_type = body.get('contentType', 'video/mp4')

        # Validate content type
        if content_type not in ALLOWED_TYPES:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid content type', 'allowedTypes': ALLOWED_TYPES}),
            }

        # Build key: {timestamp}/{userId}/{filename}
        filename = filename_path.split('/')[-1]
        timestamp = datetime.utcnow().isoformat()
        key = f"{timestamp}/{user_id}/{filename}"

        # Generate pre-signed URL — client uploads directly to S3 (no Lambda size limits)
        upload_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': key,
                'ContentType': content_type,
            },
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'uploadUrl': upload_url, 'fileKey': key}),
        }

    except KeyError as e:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': f'Missing required field: {str(e)}'}),
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'Internal server error: {str(e)}'}),
        }
