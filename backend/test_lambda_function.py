import json
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')
os.environ.setdefault('TASKS_TABLE', 'UnitTestTasks')
os.environ.setdefault('AUDIO_BUCKET', 'unit-test-audio')

import lambda_function
from botocore.exceptions import ClientError


def make_event(method, path, body=None, task_id=None):
    return {
        'requestContext': {'http': {'method': method}},
        'rawPath': path,
        'pathParameters': {'taskId': task_id} if task_id else {},
        'body': json.dumps(body) if body is not None else None,
    }


class LambdaHandlerTests(unittest.TestCase):
    def test_create_task_persists_item(self):
        table = MagicMock()
        with patch.object(lambda_function, 'TASKS_TABLE', table):
            result = lambda_function.handler(
                make_event('POST', '/tasks', {
                    'title': 'Presentation',
                    'description': 'Practice the demo',
                }),
                None,
            )

        task = json.loads(result['body'])
        self.assertEqual(result['statusCode'], 201)
        self.assertEqual(task['title'], 'Presentation')
        self.assertFalse(task['completed'])
        table.put_item.assert_called_once()

    def test_list_tasks_reads_all_query_pages(self):
        table = MagicMock()
        table.query.side_effect = [
            {'Items': [{'taskId': 'one'}], 'LastEvaluatedKey': {'taskId': 'one'}},
            {'Items': [{'taskId': 'two'}]},
        ]
        with patch.object(lambda_function, 'TASKS_TABLE', table):
            result = lambda_function.handler(make_event('GET', '/tasks'), None)

        self.assertEqual(json.loads(result['body']), [
            {'taskId': 'one'},
            {'taskId': 'two'},
        ])
        self.assertEqual(table.query.call_count, 2)

    def test_invalid_task_payload_is_rejected(self):
        table = MagicMock()
        with patch.object(lambda_function, 'TASKS_TABLE', table):
            result = lambda_function.handler(
                make_event('POST', '/tasks', {'title': '  '}),
                None,
            )

        self.assertEqual(result['statusCode'], 400)
        table.put_item.assert_not_called()

    def test_completion_updates_boolean_status(self):
        table = MagicMock()
        table.update_item.return_value = {
            'Attributes': {'taskId': 'task-1', 'completed': True},
        }
        with patch.object(lambda_function, 'TASKS_TABLE', table):
            result = lambda_function.handler(
                make_event('PATCH', '/tasks/task-1', {'completed': True}, 'task-1'),
                None,
            )

        self.assertEqual(result['statusCode'], 200)
        self.assertTrue(json.loads(result['body'])['completed'])
        self.assertIn(':completed', table.update_item.call_args.kwargs['ExpressionAttributeValues'])

    def test_missing_task_update_returns_not_found(self):
        table = MagicMock()
        table.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Not found'}},
            'UpdateItem',
        )
        with patch.object(lambda_function, 'TASKS_TABLE', table):
            result = lambda_function.handler(
                make_event('PATCH', '/tasks/missing', {'completed': True}, 'missing'),
                None,
            )

        self.assertEqual(result['statusCode'], 404)

    def test_audio_uses_a_short_lived_presigned_url(self):
        s3 = MagicMock()
        s3.generate_presigned_url.return_value = 'https://private-audio.example/signed'
        with patch.object(lambda_function, 'S3', s3):
            result = lambda_function.handler(make_event('GET', '/audio-url'), None)

        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(json.loads(result['body'])['expiresIn'], 900)
        self.assertEqual(s3.generate_presigned_url.call_args.kwargs['ExpiresIn'], 900)
        self.assertEqual(result['headers']['Access-Control-Allow-Origin'], '*')


if __name__ == '__main__':
    unittest.main()
