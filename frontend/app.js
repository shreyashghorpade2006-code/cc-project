(() => {
  const apiBase = (window.APP_CONFIG?.apiBaseUrl || '').replace(/\/$/, '');
  const taskForm = document.querySelector('#task-form');
  const titleInput = document.querySelector('#task-title');
  const descriptionInput = document.querySelector('#task-description');
  const addButton = document.querySelector('#add-button');
  const taskList = document.querySelector('#task-list');
  const message = document.querySelector('#message');
  const filters = [...document.querySelectorAll('.filter')];
  const audio = new Audio();
  audio.crossOrigin = 'anonymous';
  let tasks = [];
  let filter = 'all';
  let soundPromise;
  let soundExpiresAt = 0;

  async function api(path, options) {
    const response = await fetch(`${apiBase}${path}`, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `Request failed (${response.status}).`);
    }
    return data;
  }

  function showMessage(text, isError = false) {
    message.textContent = text;
    message.classList.toggle('error', isError);
  }

  function updateStats() {
    const completed = tasks.filter(task => task.completed).length;
    document.querySelector('#total-count').textContent = tasks.length;
    document.querySelector('#pending-count').textContent = tasks.length - completed;
    document.querySelector('#completed-count').textContent = completed;
    document.querySelector('#all-filter-count').textContent = tasks.length;
  }

  function renderTasks() {
    updateStats();
    const visible = tasks.filter(task =>
      filter === 'all' ||
      (filter === 'pending' && !task.completed) ||
      (filter === 'completed' && task.completed)
    );
    taskList.replaceChildren();

    if (!visible.length) {
      const empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = tasks.length
        ? `No ${filter} tasks yet.`
        : 'Your list is clear. Add your first task above.';
      taskList.append(empty);
      return;
    }

    visible.forEach(task => {
      const card = document.createElement('article');
      card.className = `task-card${task.completed ? ' completed' : ''}`;

      const checkbox = document.createElement('input');
      checkbox.className = 'task-check';
      checkbox.type = 'checkbox';
      checkbox.checked = task.completed;
      checkbox.setAttribute('aria-label', `Mark ${task.title} ${task.completed ? 'pending' : 'completed'}`);
      checkbox.addEventListener('change', () => toggleTask(task, checkbox.checked));

      const content = document.createElement('div');
      content.className = 'task-content';
      const title = document.createElement('h3');
      title.className = 'task-title';
      title.textContent = task.title;
      content.append(title);
      if (task.description) {
        const description = document.createElement('p');
        description.className = 'task-description';
        description.textContent = task.description;
        content.append(description);
      }
      if (task.createdAt) {
        const date = document.createElement('p');
        date.className = 'task-meta';
        const parsedDate = new Date(task.createdAt);
        date.textContent = Number.isNaN(parsedDate.getTime())
          ? ''
          : `Added ${parsedDate.toLocaleDateString()}`;
        if (date.textContent) content.append(date);
      }

      const actions = document.createElement('div');
      actions.className = 'task-actions';
      const edit = document.createElement('button');
      edit.className = 'icon-button';
      edit.type = 'button';
      edit.textContent = 'Edit';
      edit.setAttribute('aria-label', `Edit ${task.title}`);
      edit.addEventListener('click', () => editTask(task));
      const remove = document.createElement('button');
      remove.className = 'icon-button delete';
      remove.type = 'button';
      remove.textContent = 'Delete';
      remove.setAttribute('aria-label', `Delete ${task.title}`);
      remove.addEventListener('click', () => deleteTask(task));
      actions.append(edit, remove);
      card.append(checkbox, content, actions);
      taskList.append(card);
    });
  }

  async function loadTasks() {
    try {
      tasks = await api('/tasks');
      renderTasks();
    } catch (error) {
      showMessage(`Could not load tasks: ${error.message}`, true);
    }
  }

  function prepareCompletionSound() {
    soundPromise = api('/audio-url').then(audioInfo => {
      audio.src = audioInfo.url;
      audio.preload = 'auto';
      audio.load();
      soundExpiresAt = Date.now() + (audioInfo.expiresIn * 1000);
    });
    soundPromise.catch(() => {});
    return soundPromise;
  }

  async function playCompletionSound() {
    if (!soundPromise || Date.now() >= soundExpiresAt - 5000) {
      prepareCompletionSound();
    }
    await soundPromise;
    audio.currentTime = 0;
    await audio.play();
  }

  async function toggleTask(task, completed) {
    showMessage('');
    try {
      const updated = await api(`/tasks/${encodeURIComponent(task.taskId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed }),
      });
      tasks = tasks.map(item => item.taskId === updated.taskId ? updated : item);
      renderTasks();
      if (completed) {
        showMessage('Task completed successfully!');
        try {
          await playCompletionSound();
        } catch {
          showMessage('Task completed successfully! The completion sound could not be played.', true);
          soundPromise = undefined;
        }
      } else {
        showMessage('Task marked as pending.');
      }
    } catch (error) {
      showMessage(`Could not update task: ${error.message}`, true);
      renderTasks();
    }
  }

  async function editTask(task) {
    const title = window.prompt('Edit task title:', task.title);
    if (title === null) return;
    if (!title.trim()) {
      showMessage('Task title cannot be empty.', true);
      return;
    }
    const description = window.prompt('Edit task description:', task.description || '');
    if (description === null) return;
    showMessage('');
    try {
      const updated = await api(`/tasks/${encodeURIComponent(task.taskId)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), description }),
      });
      tasks = tasks.map(item => item.taskId === updated.taskId ? updated : item);
      renderTasks();
      showMessage('Task updated.');
    } catch (error) {
      showMessage(`Could not edit task: ${error.message}`, true);
    }
  }

  async function deleteTask(task) {
    showMessage('');
    try {
      await api(`/tasks/${encodeURIComponent(task.taskId)}`, { method: 'DELETE' });
      tasks = tasks.filter(item => item.taskId !== task.taskId);
      renderTasks();
      showMessage('Task deleted.');
    } catch (error) {
      showMessage(`Could not delete task: ${error.message}`, true);
    }
  }

  taskForm.addEventListener('submit', async event => {
    event.preventDefault();
    const title = titleInput.value.trim();
    if (!title) {
      showMessage('Enter a task title first.', true);
      return;
    }
    showMessage('');
    addButton.disabled = true;
    try {
      const task = await api('/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          description: descriptionInput.value.trim(),
        }),
      });
      tasks.unshift(task);
      taskForm.reset();
      filter = 'all';
      filters.forEach(button => button.classList.toggle('active', button.dataset.filter === filter));
      renderTasks();
      titleInput.focus();
      showMessage('Task added and saved.');
    } catch (error) {
      showMessage(`Could not add task: ${error.message}`, true);
    } finally {
      addButton.disabled = false;
    }
  });

  filters.forEach(button => {
    button.addEventListener('click', () => {
      filter = button.dataset.filter;
      filters.forEach(item => item.classList.toggle('active', item === button));
      renderTasks();
    });
  });

  loadTasks();
  prepareCompletionSound();
})();
