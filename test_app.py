import unittest

from app import app, db


class TodoApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        )

    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()
        self.client = app.test_client()

    def create_user(self):
        return self.client.post(
            '/users',
            json={'name': 'alice', 'email': 'alice@example.com'},
        )

    def test_api_root_returns_available_endpoints(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.content_type)
        self.assertIn(b'Cloud-Based To-Do List', response.data)
        response.close()

    def test_frontend_assets_are_served(self):
        for path in ('/app.js', '/styles.css', '/config.js'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()

    def test_local_completion_audio_is_available(self):
        audio_info = self.client.get('/api/audio-url').get_json()
        response = self.client.get(audio_info['url'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'audio/mpeg')
        self.assertGreater(len(response.data), 1000)
        response.close()

    def test_create_and_list_users(self):
        response = self.create_user()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['name'], 'alice')
        self.assertEqual(len(self.client.get('/users').get_json()), 1)

    def test_duplicate_user_name_returns_conflict(self):
        self.create_user()

        response = self.create_user()

        self.assertEqual(response.status_code, 409)

    def test_invalid_user_payload_returns_bad_request(self):
        for payload in ([], {'name': 1, 'email': 'alice@example.com'}):
            with self.subTest(payload=payload):
                response = self.client.post('/users', json=payload)
                self.assertEqual(response.status_code, 400)

    def test_todo_requires_integer_user_id(self):
        self.create_user()

        for user_id in (1.5, True, 'not-an-id', 2**63):
            with self.subTest(user_id=user_id):
                response = self.client.post(
                    '/todos',
                    json={'name': 'task', 'id_user': user_id},
                )
                self.assertEqual(response.status_code, 400)

    def test_todo_creation_and_user_deletion_cascade(self):
        user = self.create_user().get_json()
        todo_response = self.client.post(
            '/todos',
            json={'name': 'task', 'id_user': user['id_user']},
        )
        self.assertEqual(todo_response.status_code, 201)

        delete_response = self.client.delete(f"/users/{user['id_user']}")

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(self.client.get('/todos').get_json(), [])

    def test_todo_can_be_completed(self):
        user = self.create_user().get_json()
        todo = self.client.post(
            '/todos',
            json={'name': 'task', 'id_user': user['id_user']},
        ).get_json()

        response = self.client.patch(
            f"/todos/{todo['id_todo']}",
            json={'is_active': True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['is_active'])
        self.assertEqual(
            self.client.patch(
                f"/todos/{todo['id_todo']}",
                json={'is_active': 'true'},
            ).status_code,
            400,
        )

    def test_cloud_tasks_create_edit_complete_filter_and_delete(self):
        created = self.client.post(
            '/api/tasks',
            json={'title': 'Presentation', 'description': 'Prepare the AWS demo'},
        )
        self.assertEqual(created.status_code, 201)
        task = created.get_json()
        self.assertEqual(task['title'], 'Presentation')
        self.assertEqual(task['description'], 'Prepare the AWS demo')
        self.assertFalse(task['completed'])
        self.assertEqual(len(self.client.get('/api/tasks').get_json()), 1)

        updated = self.client.put(
            f"/api/tasks/{task['taskId']}",
            json={'title': 'Updated presentation', 'description': 'Practice the demo'},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()['title'], 'Updated presentation')
        self.assertEqual(updated.get_json()['description'], 'Practice the demo')

        completed = self.client.patch(
            f"/api/tasks/{task['taskId']}",
            json={'completed': True},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertTrue(completed.get_json()['completed'])

        deleted = self.client.delete(f"/api/tasks/{task['taskId']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get('/api/tasks').get_json(), [])

    def test_cloud_task_validation_and_missing_task(self):
        self.assertEqual(self.client.post('/api/tasks', json={'title': '  '}).status_code, 400)
        self.assertEqual(self.client.post('/api/tasks', json=[]).status_code, 400)
        self.assertEqual(
            self.client.patch('/api/tasks/9999', json={'completed': True}).status_code,
            404,
        )
        self.assertEqual(
            self.client.put(
                '/api/tasks/9999',
                json={'title': 'Update', 'description': ''},
            ).status_code,
            404,
        )

    def test_missing_todo_and_user_return_not_found(self):
        self.assertEqual(self.client.delete('/users/123').status_code, 404)
        self.assertEqual(self.client.delete('/todos/123').status_code, 404)


if __name__ == '__main__':
    unittest.main()
