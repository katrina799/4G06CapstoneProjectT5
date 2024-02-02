var isRunning = false;
var timer;
var start;

function startTimer(duration, display) {
    start = Date.now();
    var diff, minutes, seconds;

    function timerFunction() {

        diff = duration - (((Date.now() - start) / 1000) | 0);
        minutes = (diff / 60)| 0;
        seconds = (diff % 60)| 0;
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
    const starContainer = document.getElementById('starContainer');
    const star = document.createElement('span');
    star.className = 'star';
    star.textContent = '🍅';
    starContainer.appendChild(star);
}

window.onload = function () {
    var twentyFiveMinutes = 5 * 1, //60 * 25
        display = document.querySelector('#time');
    document.querySelector('#startBtn').onclick = function() {
        startTimer(twentyFiveMinutes, display);
    };
    document.querySelector('#resetBtn').onclick = function() {
        clearInterval(timer);
        isRunning = false;
        start = Date.now();
        display.textContent = "25:00";
    };
};
