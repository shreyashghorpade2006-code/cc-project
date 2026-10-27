import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
OWNER_ID = 'demo'
TASKS_TABLE = boto3.resource('dynamodb').Table(os.environ['TASKS_TABLE'])
S3 = boto3.client('s3')
AUDIO_BUCKET = os.environ['AUDIO_BUCKET']
AUDIO_OBJECT_KEY = os.environ.get('AUDIO_OBJECT_KEY', 'task-completed.mp3')
AUDIO_URL_TTL_SECONDS = 900


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def response(status_code, payload=None):
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'content-type',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS',
    }
    return {
        'statusCode': status_code,
        'headers': headers,
        'body': '' if payload is None else json.dumps(payload),
    }


def parse_body(event):
    body = event.get('body')
    if event.get('isBase64Encoded') and body:
        body = base64.b64decode(body).decode('utf-8')
    if not body:
        return {}
    try:
        parsed = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def valid_text(value, maximum, required=False):
    return (
        isinstance(value, str)
        and (not required or bool(value.strip()))
        and len(value.strip()) <= maximum
    )


def list_tasks():
    tasks = []
    query = {'KeyConditionExpression': Key('ownerId').eq(OWNER_ID)}
    while True:
        result = TASKS_TABLE.query(**query)
        tasks.extend(result.get('Items', []))
        last_key = result.get('LastEvaluatedKey')
        if not last_key:
            return response(200, tasks)
        query['ExclusiveStartKey'] = last_key


def create_task(data):
    if data is None:
        return response(400, {'error': 'request body must be a JSON object'})
    title = data.get('title')
    description = data.get('description', '')
    if not valid_text(title, 100, required=True):
        return response(400, {'error': 'title is required and must be at most 100 characters'})
    if not valid_text(description, 2000):
        return response(400, {'error': 'description must be at most 2000 characters'})

    timestamp = now_iso()
    task = {
        'ownerId': OWNER_ID,
        'taskId': str(uuid.uuid4()),
        'title': title.strip(),
        'description': description.strip(),
        'completed': False,
        'createdAt': timestamp,
        'updatedAt': timestamp,
    }
    TASKS_TABLE.put_item(Item=task)
    return response(201, task)


def update_task(task_id, method, data):
    if data is None:
        return response(400, {'error': 'request body must be a JSON object'})

    timestamp = now_iso()
    if method == 'PATCH':
        completed = data.get('completed')
        if not isinstance(completed, bool):
            return response(400, {'error': 'completed must be a boolean'})
        update_expression = 'SET completed = :completed, updatedAt = :updatedAt'
        values = {':completed': completed, ':updatedAt': timestamp}
    else:
        title = data.get('title')
        description = data.get('description', '')
        if not valid_text(title, 100, required=True):
            return response(400, {'error': 'title is required and must be at most 100 characters'})
        if not valid_text(description, 2000):
            return response(400, {'error': 'description must be at most 2000 characters'})
        update_expression = (
            'SET title = :title, description = :description, updatedAt = :updatedAt'
        )
        values = {
            ':title': title.strip(),
            ':description': description.strip(),
            ':updatedAt': timestamp,
        }

    try:
        result = TASKS_TABLE.update_item(
            Key={'ownerId': OWNER_ID, 'taskId': task_id},
            UpdateExpression=update_expression,
            ConditionExpression='attribute_exists(taskId)',
            ExpressionAttributeValues=values,
            ReturnValues='ALL_NEW',
        )
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            return response(404, {'error': 'task not found'})
        raise
    return response(200, result['Attributes'])


def delete_task(task_id):
    try:
        TASKS_TABLE.delete_item(
            Key={'ownerId': OWNER_ID, 'taskId': task_id},
            ConditionExpression='attribute_exists(taskId)',
        )
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            return response(404, {'error': 'task not found'})
        raise
    return response(200, {'message': 'task deleted'})


def audio_url():
    url = S3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': AUDIO_BUCKET,
            'Key': AUDIO_OBJECT_KEY,
            'ResponseContentType': 'audio/mpeg',
        },
        ExpiresIn=AUDIO_URL_TTL_SECONDS,
    )
    return response(200, {'url': url, 'expiresIn': AUDIO_URL_TTL_SECONDS})


def handler(event, _context):
    request_context = event.get('requestContext', {})
    method = request_context.get('http', {}).get('method', event.get('httpMethod', ''))
    path = event.get('rawPath', event.get('path', '/'))
    task_id = event.get('pathParameters', {}).get('taskId')
    request_id = getattr(_context, 'aws_request_id', 'local')
    LOGGER.info('Handling %s %s (request %s)', method, path, request_id)

    if method == 'OPTIONS':
        return response(204)
    if path == '/tasks' and method == 'GET':
        return list_tasks()
    if path == '/tasks' and method == 'POST':
        return create_task(parse_body(event))
    if path == '/audio-url' and method == 'GET':
        return audio_url()
    if path.startswith('/tasks/') and task_id:
        if method in ('PATCH', 'PUT'):
            return update_task(task_id, method, parse_body(event))
        if method == 'DELETE':
            return delete_task(task_id)
    return response(404, {'error': 'route not found'})
