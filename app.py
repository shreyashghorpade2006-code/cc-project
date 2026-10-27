from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect, text

# Initialize Flask app
app = Flask(__name__)

# Configure the database using SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@app.route('/')
def index():
    return send_from_directory('frontend', 'index.html')


@app.route('/styles.css')
def styles():
    return send_from_directory('frontend', 'styles.css')


@app.route('/app.js')
def frontend_script():
    return send_from_directory('frontend', 'app.js')


@app.route('/config.js')
def frontend_config():
    return send_from_directory('frontend', 'config.js')


# Define User Database Model
class User(db.Model):
    """
    User model represnets appliacation users.
    Each user has multiple todos (one-to-many relationship)
    """
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relation to Todo
    todos = db.relationship(
        'Todo',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan',
    )

# Define Todo Database Model
class Todo(db.Model):
    """
    Todp model represents tasks associated with users.
    Each todo is linked to a user via foreign key.
    """
    __tablename__ = 'todos'
    todo_id  = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(2000), nullable=False, default='')
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    id_user = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)


def ensure_local_task_schema():
    db.create_all()
    columns = {column['name'] for column in inspect(db.engine).get_columns('todos')}
    if 'description' not in columns:
        with db.engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE todos ADD COLUMN description VARCHAR(2000) NOT NULL DEFAULT ''"
            ))


def get_local_demo_user():
    user = User.query.order_by(User.user_id).first()
    if user:
        return user

    user = User(name='Demo User', email='demo@example.com')
    db.session.add(user)
    db.session.commit()
    return user


def serialize_local_task(todo):
    return {
        'taskId': str(todo.todo_id),
        'title': todo.name,
        'description': todo.description,
        'completed': todo.is_active,
        'createdAt': todo.created_at.isoformat() if todo.created_at else '',
        'updatedAt': todo.updated_at.isoformat() if todo.updated_at else '',
    }


@app.route('/api/tasks', methods=['GET', 'POST'])
def local_tasks():
    ensure_local_task_schema()
    user = get_local_demo_user()

    if request.method == 'GET':
        tasks = Todo.query.filter_by(id_user=user.user_id).order_by(Todo.created_at.desc()).all()
        return jsonify([serialize_local_task(task) for task in tasks])

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'request body must be a JSON object'}), 400

    title = data.get('title')
    description = data.get('description', '')
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 100:
        return jsonify({'error': 'title is required and must be at most 100 characters'}), 400
    if not isinstance(description, str) or len(description) > 2000:
        return jsonify({'error': 'description must be at most 2000 characters'}), 400

    task = Todo(
        name=title.strip(),
        description=description.strip(),
        is_active=False,
        id_user=user.user_id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(serialize_local_task(task)), 201


@app.route('/api/tasks/<int:task_id>', methods=['PATCH', 'PUT', 'DELETE'])
def local_task(task_id):
    ensure_local_task_schema()
    user = get_local_demo_user()
    task = Todo.query.filter_by(todo_id=task_id, id_user=user.user_id).first()
    if not task:
        return jsonify({'error': 'task not found'}), 404

    if request.method == 'DELETE':
        db.session.delete(task)
        db.session.commit()
        return jsonify({'message': 'task deleted'})

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'request body must be a JSON object'}), 400

    if request.method == 'PATCH':
        completed = data.get('completed')
        if not isinstance(completed, bool):
            return jsonify({'error': 'completed must be a boolean'}), 400
        task.is_active = completed
    else:
        title = data.get('title')
        description = data.get('description', '')
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 100:
            return jsonify({'error': 'title is required and must be at most 100 characters'}), 400
        if not isinstance(description, str) or len(description) > 2000:
            return jsonify({'error': 'description must be at most 2000 characters'}), 400
        task.name = title.strip()
        task.description = description.strip()

    db.session.commit()
    return jsonify(serialize_local_task(task))


@app.route('/api/audio-url', methods=['GET'])
def local_audio_url():
    return jsonify({'url': '/completion-audio', 'expiresIn': 3600})


@app.route('/completion-audio', methods=['GET'])
def completion_audio():
    return send_from_directory(
        app.root_path,
        'task-completed.mp3',
        mimetype='audio/mpeg',
    )


# User Endpoint
@app.route('/users', methods=['POST'])
def add_user():
    """
    Create a new user with name and email.
    Returns 200 if successful, 400 if input is invalid.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    name = data.get('name')
    email = data.get('email')
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name and email are required!"}), 400
    if not isinstance(email, str) or not email.strip():
        return jsonify({"error": "name and email are required!"}), 400

    user = User(name=name.strip(), email=email.strip())
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "a user with this name already exists"}), 409

    return jsonify({
        "id_user": user.user_id,
        "name": user.name,
        "email": user.email
    }), 201
    
@app.route('/users', methods=['GET'])
def get_users():
    """
    Retrieve all users from the database.
    Returns a list of users with their id, name, and email.
    """
    users = User.query.all()
    return jsonify([
        {
            "id_user": u.user_id,
            "name": u.name,
            "email": u.email,
        }
        for u in users
    ]), 200
    

@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """
    Delete a user by user_id.
    Returns 200 if successful, 404 if user is not found.
    """
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "user is not found!"}), 404
    
    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "user deleted successfully"}), 200


# ToDo Endpoint
@app.route('/todos', methods=['POST'])
def add_todo():
    """
    Create a new todo item.
    Requires 'name' and 'id_user' in the request body.
    Returns 201 if successful, 400 if input is invalid or user not found.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    name = data.get('name')
    id_user = data.get('id_user')
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name is required!"}), 400
    if id_user is None:
        return jsonify({"error": "id_user is required!"}), 400
    if isinstance(id_user, bool) or not isinstance(id_user, (int, str)):
        return jsonify({"error": "id_user should be an integer!"}), 400

    try:
        id_user_int = int(id_user)
    except ValueError:
        return jsonify({"error": "id_user should be an integer!"}), 400

    if not -(2**63) <= id_user_int < 2**63:
        return jsonify({"error": "id_user should be an integer!"}), 400

    user = db.session.get(User, id_user_int)
    if not user:
        return jsonify({"error": "user not found!"}), 400

    new_todo = Todo(name=name.strip(), id_user=id_user_int, is_active=False)
    db.session.add(new_todo)
    db.session.commit()

    return jsonify({
        "id_todo": new_todo.todo_id,
        "name": new_todo.name,
        "is_active": new_todo.is_active,
        "user_id": new_todo.id_user
    }), 201
    
@app.route('/todos', methods=['GET'])
def get_todo():
    """
    Retrieve all todo items.
    Returns a list of todos with their id, name, is_active status, and user_id
    """
    todos = Todo.query.all()
    return jsonify([
        {
        "id_todo": t.todo_id,
        "name": t.name,
        "is_active": t.is_active,
        "user_id": t.id_user
        }
        for t in todos
    ]), 200


@app.route('/todos/<int:todo_id>', methods=['PATCH'])
def update_todo(todo_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('is_active'), bool):
        return jsonify({"error": "is_active must be a boolean"}), 400

    todo = db.session.get(Todo, todo_id)
    if not todo:
        return jsonify({"error": "todo is not found!"}), 404

    todo.is_active = data['is_active']
    db.session.commit()
    return jsonify({
        "id_todo": todo.todo_id,
        "name": todo.name,
        "is_active": todo.is_active,
        "user_id": todo.id_user,
    }), 200


@app.route('/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """
    Delete a todo item by todo_id.
    Returns 200 if successful, 404 if todo is not found.
    """
    todo = db.session.get(Todo, todo_id)
    if not todo:
        return jsonify({"error": "todo is not found!"}), 404
    
    db.session.delete(todo)
    db.session.commit()

    return jsonify({"message": "todo deleted successfully"}), 200

# run the flask app
if __name__ == "__main__":
    app.run(debug=True)