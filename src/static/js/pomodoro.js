var isRunning = false;
var timer;
var start;

let currentAudio = null;
let isPlaying = false;

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
}

function updateTomatoCount(day) {
    fetch(`/update_tomato/${day}`, { method: 'POST' })
        .then(() => loadWeeklyData())
        .catch(error => console.error('Error:', error));
}


function loadWeeklyData() {
    const staticWeeklyData = {
        "Monday": 4,
        "Tuesday": 3,
        "Wednesday": 5,
        "Thursday": 0,
        "Friday": 3,
        "Saturday": 0,
        "Sunday": 1
    };

    const maxCount = Math.max(...Object.values(staticWeeklyData));
    const weeklyDataContainer = document.getElementById('weeklyData');
    weeklyDataContainer.innerHTML = '';

    for (const [day, count] of Object.entries(staticWeeklyData)) {
        const barWidth = (count / maxCount) * 80;
        const barHtml = `
            <div class="day-container">
                <div class="bar" id="${day.toLowerCase()}-bar" style="width: ${barWidth}%;"></div>
                <span> ${day}: ${count} </span>
            </div>
        `;

        // Append the bar to the container
        weeklyDataContainer.innerHTML += barHtml;
    }
}

window.onload = function () {

    loadWeeklyData()
    var timeInvertal = 60 * 25, //60 * 25
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
