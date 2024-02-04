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
    fetch('/get_weekly_data')
        .then(response => response.json())
        .then(data => {
            const weeklyDataList = document.getElementById('weeklyData');
            weeklyDataList.innerHTML = '';
            for (const [day, count] of Object.entries(data)) {
                weeklyDataList.innerHTML += `<li>${day}: ${count} tomatoes</li>`;
            }
        })
        .catch(error => console.error('Error:', error));
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

    document.addEventListener('DOMContentLoaded', function() {
        loadWeeklyData();
    });
    

};
