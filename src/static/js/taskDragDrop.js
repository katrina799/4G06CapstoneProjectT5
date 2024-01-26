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
    const newStatus = e.target.getAttribute('data-status');
    e.target.appendChild(draggableElement);
    updateTaskStatus(id, newStatus);
}

function updateTaskStatus(taskId, newStatus) {
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
        alert(data.message); 
    })
    .catch(error => {
        console.error('Error updating task status:', error);
        alert('Failed to update task status.'); 
    });
}

