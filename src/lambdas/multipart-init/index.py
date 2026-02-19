import json
import math
import boto3
import os
from datetime import datetime, UTC

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ['BUCKET_NAME']
REGION = os.environ['REGION']

ALLOWED_TYPES = ['video/mp4', 'video/mov']
PART_SIZE = 100 * 1024 * 1024  # 100 MB per part
PRESIGNED_URL_EXPIRY = 3600    # 1 hour (parts may take longer to upload)


def handler(event, context):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'POST,OPTIONS',
    }

    try:
        http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', '')
        if http_method == 'OPTIONS':
            return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': 'CORS preflight successful'})}

        raw_body = event.get('body') or event
        body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body

        filename_path = body.get('filename', 'video.mp4')
        user_id = body.get('userId', 'anonymous')
        content_type = body.get('contentType', 'video/mp4')
        file_size = int(body.get('fileSize', 0))

        if content_type not in ALLOWED_TYPES:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid content type', 'allowedTypes': ALLOWED_TYPES}),
            }

        if file_size <= 0:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'fileSize must be a positive integer (bytes)'}),
            }

        # Build key: {timestamp}/{userId}/{filename}
        filename = filename_path.split('/')[-1]
        timestamp = datetime.now(UTC)
        key = f"{timestamp}/{user_id}/{filename}"

        # Create multipart upload
        response = s3_client.create_multipart_upload(
            Bucket=BUCKET_NAME,
            Key=key,
            ContentType=content_type,
        )
        upload_id = response['UploadId']

        # Generate pre-signed URL for each part (client uploads parts directly to S3)
        part_count = math.ceil(file_size / PART_SIZE)
        presigned_urls = []
        for part_number in range(1, part_count + 1):
            url = s3_client.generate_presigned_url(
                'upload_part',
                Params={
                    'Bucket': BUCKET_NAME,
                    'Key': key,
                    'UploadId': upload_id,
                    'PartNumber': part_number,
                },
                ExpiresIn=PRESIGNED_URL_EXPIRY,
            )
            presigned_urls.append({'partNumber': part_number, 'uploadUrl': url})

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'uploadId': upload_id,
                'fileKey': key,
                'partSize': PART_SIZE,
                'partCount': part_count,
                'presignedUrls': presigned_urls,
            }),
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