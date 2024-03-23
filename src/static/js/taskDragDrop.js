document.addEventListener('DOMContentLoaded', (event) => {
    let tasks = document.querySelectorAll('.task-card');
    let columns = document.querySelectorAll('.task-column');

    tasks.forEach(task => {
        task.addEventListener('dragstart', dragStart);
        task.addEventListener('dragend', dragEnd);
    });

    columns.forEach(column => {
        column.addEventListener('dragover', dragOver);
        column.addEventListener('dragenter', dragEnter);
        column.addEventListener('dragleave', dragLeave);
        column.addEventListener('drop', drop);
    });

    document.addEventListener('click', function (event) {
        contextMenu.style.display = 'none';
    });

    document.querySelectorAll('.task-card').forEach(function (element) {
        element.addEventListener('contextmenu', function (event) {
            event.preventDefault();
            const taskCardElement = event.target.closest('.task-card');
            const taskId = taskCardElement ? taskCardElement.getAttribute('data-id') : null; 
            sessionStorage.setItem('selectedTaskId', taskId);
            document.getElementById('contextMenu').style.display = 'block';
            document.getElementById('contextMenu').style.left = `${event.pageX}px`;
            document.getElementById('contextMenu').style.top = `${event.pageY}px`;
        });
    });
    
    

    document.addEventListener('click', function (event) {
        document.getElementById('contextMenu').style.display = 'none';
    });

    document.getElementById('deleteTask').addEventListener('click', function () {
        const taskId = sessionStorage.getItem('selectedTaskId');
        if (taskId) {
            fetch(`/delete_task/${taskId}`, {
                method: 'POST',
            }).then(response => {
                if (response.ok) {
                    location.reload();
                } else {
                    alert('Failed to delete the task.');
                }
            }).catch(error => {
                alert('Error: ' + error);
            });
        }
    });

    document.getElementById('editTask').addEventListener('click', function () {
        const taskId = sessionStorage.getItem('selectedTaskId');
        if (taskId) {
            editTask(taskId);
        }
    });
});

function dragStart(e) {
    e.dataTransfer.setData('text/plain', e.target.getAttribute('data-id'));
    setTimeout(() => {
        e.target.classList.add('hide');
    }, 0);
}

function dragEnd(e) {
    e.target.classList.remove('hide');
}

function dragOver(e) {
    e.preventDefault();
}

function dragEnter(e) {
    e.preventDefault();
    e.target.classList.add('hovered');
}

function dragLeave(e) {
    e.target.classList.remove('hovered');
}

function drop(e) {
    e.preventDefault();
    e.target.classList.remove('hovered');

    const id = e.dataTransfer.getData('text/plain');
    const draggableElement = document.querySelector(`[data-id="${id}"]`);
    const targetColumn = e.target.closest('.task-column'); 
    const sourceColumnId = draggableElement.closest('.task-column').getAttribute('id');
    const newStatus = targetColumn.getAttribute('data-status');

    if (!targetColumn || !targetColumn.classList.contains('task-column')) {
        console.error('Dropped on a non-column element:', e.target);
        return; 
    }

    targetColumn.appendChild(draggableElement);
    updateTaskStatus(id, newStatus, sourceColumnId, targetColumn.id);
}


function updateTaskStatus(taskId, newStatus, sourceColumnId, targetColumnId) {
    taskId = parseInt(taskId);
    fetch('/update_task_status', {
        method: 'POST',
        body: JSON.stringify({ id: taskId, status: newStatus }),
        headers: {
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        console.log(data); 
        if (data.message === "Task status updated successfully") {
            if (sourceColumnId !== targetColumnId) { 
                updateTaskCount(sourceColumnId, -1); 
                updateTaskCount(targetColumnId, 1); 
            }
        } else {
            alert(data.message); 
            document.getElementById(sourceColumnId).appendChild(draggableElement);
        }
    })
    .catch(error => {
        console.error('Error updating task status:', error);
        alert('Failed to update task status.'); 
        document.getElementById(sourceColumnId).appendChild(draggableElement);
    });
}

function updateTaskCount(columnId, change) {
    let column = document.getElementById(columnId);
    let taskCounter = column.querySelector('.task-count');
    let currentCount = parseInt(taskCounter.textContent) || 0;
    taskCounter.textContent = currentCount + change;
}

function editTask(taskId) {
    // Find the task element using its data-id attribute
    const taskCardElement = document.querySelector(`.task-card[data-id="${taskId}"]`);
    if (!taskCardElement) {
        alert("Task not found!");
        return;
    }

    // Extract the data from the task element
    const headerContent = taskCardElement.querySelector('.task-header').textContent.trim();
    const [courseName, taskName] = headerContent.split(' - ').map(s => s.trim());
    const taskDueDate = taskCardElement.querySelector('.task-metadata span:first-child').textContent.replace('Due: ', '').trim();
    const taskWeight = taskCardElement.querySelector('.task-metadata span:nth-child(2)').textContent.replace('Weight: ', '').trim();
    const taskEstHours = taskCardElement.querySelector('.task-metadata span:nth-child(3)').textContent.replace('Est. Time: ', '').trim();

    // Get the modal and form elements
    const editModal = document.getElementById('edit-task-modal');
    const editForm = editModal.querySelector('form'); 

    // Populate the form fields
    editForm.querySelector('input[name="course_name"]').value = courseName;
    editForm.querySelector('input[name="task_name"]').value = taskName;
    editForm.querySelector('input[name="due_date"]').value = taskDueDate || ''; 
    editForm.querySelector('input[name="weight"]').value = taskWeight;
    editForm.querySelector('input[name="est_hours"]').value = taskEstHours;
   
    showEditModal();

    editForm.onsubmit = function(event) {
        event.preventDefault();

        const formData = new FormData(editForm);

        fetch(`/edit_task/${taskId}`, {
            method: 'POST',
            body: formData,
            headers: {
                'Accept': 'application/json', 
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => { throw new Error(text) });
            }
            return response.json(); 
        })
        .then(data => {
            if (data.message) {
                location.reload(); 
            }
        })
        .catch(error => {
            console.error('There has been a problem with your fetch operation:', error);
            alert(`Error updating task: ${error.message}`);
        });
    
        closeEditModal();
    };
}

function showEditModal() {
    const editModal = document.getElementById('edit-task-modal');
    const modalOverlay = document.getElementById('modal-overlay');

    editModal.style.display = 'block';
    modalOverlay.style.display = 'block';

    modalOverlay.onclick = function() {
        closeEditModal();
    }
}

function closeEditModal() {
    const editModal = document.getElementById('edit-task-modal');
    const modalOverlay = document.getElementById('modal-overlay');

    editModal.style.display = 'none';
    modalOverlay.style.display = 'none';
}

document.getElementById('show-add-task-modal-btn').onclick = function() {
    showAddModal();
}

function showAddModal() {
    document.getElementById('add-task-modal').style.display = 'block';
    document.getElementById('modal-overlay').style.display = 'block';
}

function closeAddModal() {
    document.getElementById('add-task-modal').style.display = 'none';
    document.getElementById('modal-overlay').style.display = 'none';
}

function startStudy(estTime) {
    window.location.href = '/pomodoro_page?est_time=' + encodeURIComponent(estTime);
}
