var isRunning = false;
var timer;
var start;

let currentAudio = null;
let isPlaying = false;

function updateTomatoCount(day) {
    fetch(`/update_tomato/${day}`, { method: 'POST' })
        .then(() => loadWeeklyData())
        .catch(error => console.error('Error:', error));
}

function startTimer(duration, display) {
    start = Date.now();
    var diff, minutes, seconds;
    function timerFunction() {

        diff = duration - (((Date.now() - start) / 1000) | 0);
        minutes = (diff / 60) | 0;
        seconds = (diff % 60) | 0;
        minutes = minutes < 10 ? "0" + minutes : minutes;
        seconds = seconds < 10 ? "0" + seconds : seconds;
        display.textContent = minutes + ":" + seconds;
        if (diff <= 0) {
            clearInterval(timer);
            addStar();
            isRunning = false;
        }
    };
    if (!isRunning) {
        clearInterval(timer);
        isRunning = true;
        timer = setInterval(timerFunction, 1000);
    }
}

function addStar() {
    const tomatoContainer = document.getElementById('tomatoContainer');
    const tomato = document.createElement('span');
    tomato.className = 'tomato';
    tomato.textContent = '🍅';
    tomatoContainer.appendChild(tomato);
    //update the day on wwklyMap
    const dayOfWeek = new Date().getUTCDay();
    console.log(dayOfWeek)
    const daysMap =  ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday',
    'Thursday', 'Friday']
    const day = daysMap[dayOfWeek];
    updateTomatoCount(day);
}

function updateTomatoCount(day) {
    fetch(`/update_tomato/${day}`, { method: 'POST' })
        .then(response => {
            if (response.ok) {
                // After updating the count, reload the weekly data to update the visualization
                loadWeeklyData();
            } else {
                console.error('Error updating tomato count:', response);
            }
        })
        .catch(error => console.error('Error:', error));
}

function loadWeeklyData() {

    fetch('/get_weekly_data')
        .then(response => response.json())
        .then(data => {
            const maxCount = Math.max(...data.map(item => item.count));
            const weeklyDataContainer = document.getElementById('weeklyDataContainer');
            weeklyDataContainer.innerHTML = '';

            for (const item of data) {
                // Use percentage for width
                const barWidth = (item.count / maxCount) * 100;
                const barHtml = `
            <div class="day-container">
                <span class="day-label">${item.day}</span>
                <div class="bar" style="width: ${barWidth}%;">${item.count}</div>
            </div>
        `;
                weeklyDataContainer.innerHTML += barHtml;
            }
        })
        .catch(error => console.error('Error:', error));
}

window.onload = function () {

    loadWeeklyData()
    var timeInvertal = 5 * 1, //60 * 25
        display = document.querySelector('#time');
    document.querySelector('#startBtn').onclick = function () {
        startTimer(timeInvertal, display);
    };
    document.querySelector('#resetBtn').onclick = function () {
        clearInterval(timer);
        isRunning = false;
        start = Date.now();
        display.textContent = "25:00";
    };

    document.getElementById('playMusic').addEventListener('click', function () {
        const musicSelect = document.getElementById('musicSelect');
        const selectedMusic = musicSelect.value;
        if (!currentAudio || currentAudio.src !== selectedMusic) {
            if (currentAudio) {
                currentAudio.pause();
            }
            currentAudio = new Audio(selectedMusic);
        }
        if (isPlaying) {
            currentAudio.pause();
            this.textContent = 'Play Music';
            isPlaying = false;
        } else {
            currentAudio.play();
            this.textContent = 'Pause Music';
            isPlaying = true;
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        loadWeeklyData();
    });


};
