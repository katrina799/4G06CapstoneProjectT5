document.addEventListener('DOMContentLoaded', function () {

    fetch('/get-order')
        .then(response => response.json())
        .then(orderArray => {
            let appGrid = document.getElementById('app-grid');
            let tiles = appGrid.children;
            let tilesArray = Array.from(tiles);

            tilesArray.sort(function (a, b) {
                let aIndex = parseInt(a.id.replace('app-tile', ''));
                let bIndex = parseInt(b.id.replace('app-tile', ''));
                let aOrder = orderArray.indexOf(aIndex);
                let bOrder = orderArray.indexOf(bIndex);
                return aOrder - bOrder;
            });

            while (appGrid.firstChild) {
                appGrid.removeChild(appGrid.firstChild);
            }

            tilesArray.forEach(function (tile) {
                appGrid.appendChild(tile);
            });
        })
        .catch(error => console.error('Error fetching order array:', error));

    function saveNewOrder() {
        let tiles = document.querySelectorAll('.app-tile');
        let orderArray = Array.from(tiles).map(tile => parseInt(tile.id.replace('app-tile', '')));

        fetch('/update-order', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(orderArray),
        })
            .then(response => response.json())
            .then(data => console.log(data))
            .catch((error) => {
                console.error('Error:', error);
            });
    }

    let draggedElement = null;

    function handleDragStart(e) {
        this.style.opacity = '0.4';
        draggedElement = this;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text', this.id);
    }

    function handleDragOver(e) {
        console.log("drag is over")
        if (e.preventDefault) {
            e.preventDefault();
        }
        e.dataTransfer.dropEffect = 'move';
        return false;
    }

    function handleDragEnter(e) {
        this.classList.add('over');
    }

    function handleDragLeave(e) {
        var relatedTarget = e.relatedTarget;
        console.log("left " + relatedTarget);

        if (!this.contains(relatedTarget)) {
            this.classList.remove('over');
        }
    }

    function handleDrop(e) {
        console.log("dropped " + this);
        if (e.stopPropagation) {
            e.stopPropagation();
        }
        if (draggedElement !== this) {
            let savedHref = this.href;
            let savedHTML = this.innerHTML;
            let savedID = this.id;
            this.href = draggedElement.href;
            this.innerHTML = draggedElement.innerHTML;
            this.id = draggedElement.id;
            draggedElement.href = savedHref;
            draggedElement.innerHTML = savedHTML;
            draggedElement.id = savedID;
        }

        draggedElement.style.opacity = '1';
        items.forEach(function (item) {
            item.classList.remove('over');
        });

        saveNewOrder();

        return false;
    }

    function handleDragEnd(e) {
        console.log("drag end")
        draggedElement.style.opacity = '1';
        items.forEach(function (item) {
            item.classList.remove('over');
        });
    }

    let items = document.querySelectorAll('.app-grid-container .app-tile');
    items.forEach(function (item) {
        item.setAttribute('draggable', 'true');
        item.addEventListener('dragstart', handleDragStart, false);
        item.addEventListener('dragenter', handleDragEnter, false);
        item.addEventListener('dragover', handleDragOver, false);
        item.addEventListener('dragleave', handleDragLeave, false);
        item.addEventListener('drop', handleDrop, false);
        item.addEventListener('dragend', handleDragEnd, false);
    });
});