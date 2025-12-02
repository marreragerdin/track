const toggleButton = document.getElementById("toggle-btn");
const sidebar = document.getElementById("sidebar");

function toggleSidebar() {
    sidebar.classList.toggle("close");
    toggleButton.classList.toggle("rotate");
    closeAllSubMenus();
}

function handleResize() {
    if (window.innerWidth <= 800) {
        sidebar.classList.remove("close");
    }
}
window.addEventListener("resize", handleResize);
handleResize();

function toggleSubMenu(button) {
    if (!button.nextElementSibling.classList.contains("show")) {
        closeAllSubMenus();
    }
    button.nextElementSibling.classList.toggle("show");
    button.classList.toggle("rotate");

    if (sidebar.classList.contains("close")) {
        sidebar.classList.toggle("close");
        toggleButton.classList.toggle("rotate");
    } 
}

function closeAllSubMenus() {
    Array.from(sidebar.getElementsByClassName("show")).forEach(ul => {
        ul.classList.remove("show");
        ul.previousElementSibling.classList.remove("rotate");
    });
}

const hamburgerBtn = document.createElement("button");
hamburgerBtn.id = "hamburger-btn";
hamburgerBtn.innerHTML = `<span></span><span></span><span></span>`;
document.body.appendChild(hamburgerBtn);

const overlay = document.createElement("div");
overlay.id = "overlay";
document.body.appendChild(overlay);

hamburgerBtn.addEventListener("click", () => {
    hamburgerBtn.classList.toggle("active");
    sidebar.classList.toggle("show");
    overlay.classList.toggle("show");
});

overlay.addEventListener("click", () => {
    hamburgerBtn.classList.remove("active");
    sidebar.classList.remove("show");
    overlay.classList.remove("show");
});

const trendCtx = document.getElementById('trendChart').getContext('2d');
const trendGradient = trendCtx.createLinearGradient(0, 0, trendCtx.canvas.width, 0);
trendGradient.addColorStop(0, '#2872CB');
trendGradient.addColorStop(1, '#01277E');

new Chart(trendCtx, {
    type: 'line',
    data: {
        labels: ['Jan','Feb','Mar','Apr','May','June','July'],
        datasets: [{
            label: 'Average Ratings',
            data: [3.5, 4.0, 4.5, 3.5, 4.0, 4.1, 4.5],
            borderColor: trendGradient,    
            backgroundColor: 'rgba(40,114,203,0.2)', 
            fill: true,
            tension: 0.3
        }]
    },
    options: {
        responsive: true,
        plugins: { 
            legend: { 
                display: false,
                labels: { font: { family: 'Poppins' } } 
            }
        },
        scales: { 
            y: { 
                min: 0, 
                max: 5,
                ticks: { font: { family: 'Poppins' } } 
            },
            x: { 
                ticks: { font: { family: 'Poppins' } } 
            }
        }
    }
});

const regionCtx = document.getElementById('regionChart').getContext('2d');
const regionGradient = regionCtx.createLinearGradient(0, 0, 0, regionCtx.canvas.height);
regionGradient.addColorStop(0, '#2872CB'); // top
regionGradient.addColorStop(1, '#01277E'); // bottom

new Chart(regionCtx, {
    type: 'bar',
    data: {
        labels: ['NCR','III','I','VII','VI'],
        datasets: [{
            label: 'Responses',
            data: [250,230,190,140,70],
            backgroundColor: regionGradient
        }]
    },
    options: {
        responsive: true,
        plugins: { 
            legend: { 
                display: false,
                labels: { font: { family: 'Poppins' } }
            }
        },
        scales: {
            y: { ticks: { font: { family: 'Poppins' } } },
            x: { ticks: { font: { family: 'Poppins' } } }
        }
    }
});


const timelineBtn = document.querySelector('.timeline-btn');
const timelineText = timelineBtn.querySelector('.timeline-text');
const timelineOptions = document.querySelector('.timeline-options');

timelineBtn.addEventListener('click', () => {
    timelineBtn.classList.toggle('active');
    timelineOptions.style.display = timelineOptions.style.display === 'block' ? 'none' : 'block';
});

timelineOptions.querySelectorAll('li').forEach(option => {
    option.addEventListener('click', () => {
        timelineText.textContent = option.textContent;
        timelineBtn.classList.remove('active');
        timelineOptions.style.display = 'none';
        console.log("Selected:", option.dataset.value);
    });
});

document.addEventListener('click', (e) => {
    if (!e.target.closest('.timeline-dropdown')) {
        timelineBtn.classList.remove('active');
        timelineOptions.style.display = 'none';
    }
});