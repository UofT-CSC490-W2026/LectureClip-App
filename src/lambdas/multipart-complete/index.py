import json
import boto3
import os

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ['BUCKET_NAME']
REGION = os.environ['REGION']


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

        file_key = body.get('fileKey')
        upload_id = body.get('uploadId')
        # parts: [{"PartNumber": 1, "ETag": "..."}, ...]
        parts = body.get('parts')

        if not all([file_key, upload_id, parts]):
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Missing required fields: fileKey, uploadId, parts'}),
            }

        response = s3_client.complete_multipart_upload(
            Bucket=BUCKET_NAME,
            Key=file_key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts},
        )

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'fileKey': file_key,
                'location': response.get('Location', ''),
                'bucket': response.get('Bucket', BUCKET_NAME),
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