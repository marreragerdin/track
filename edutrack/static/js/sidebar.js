const sidebar = document.getElementById("sidebar");
const toggleButton = document.getElementById("toggle-btn");
const SIDEBAR_STATE_KEY = "sidebar_collapsed";

function applyStoredSidebarState() {
    if (!sidebar || !toggleButton) return;
    const stored = localStorage.getItem(SIDEBAR_STATE_KEY);
    if (stored === null) return;

    const collapsed = stored === "1";
    if (collapsed) {
        sidebar.classList.add("close");
        toggleButton.classList.add("rotate");
    } else {
        sidebar.classList.remove("close");
        toggleButton.classList.remove("rotate");
    }
}

function toggleSidebar() {
    if (!sidebar || !toggleButton) return;
    sidebar.classList.toggle("close");
    toggleButton.classList.toggle("rotate");
    closeAllSubMenus();
    localStorage.setItem(
        SIDEBAR_STATE_KEY,
        sidebar.classList.contains("close") ? "1" : "0"
    );
}

function handleResize() {
    if (!sidebar) return;
    // Only auto-adjust on small screens if user hasn't explicitly chosen a state
    const stored = localStorage.getItem(SIDEBAR_STATE_KEY);
    if (stored !== null) return;
    if (window.innerWidth <= 800) {
        sidebar.classList.remove("close");
        if (toggleButton) toggleButton.classList.remove("rotate");
    }
}

window.addEventListener("resize", handleResize);
applyStoredSidebarState();
handleResize();

function toggleSubMenu(button) {
    if (!sidebar || !button || !button.nextElementSibling) return;

    if (!button.nextElementSibling.classList.contains("show")) {
        closeAllSubMenus();
    }
    button.nextElementSibling.classList.toggle("show");
    button.classList.toggle("rotate");

    if (sidebar.classList.contains("close")) {
        sidebar.classList.toggle("close");
        if (toggleButton) {
            toggleButton.classList.toggle("rotate");
        }
    } 
}

function closeAllSubMenus() {
    if (!sidebar) return;
    Array.from(sidebar.getElementsByClassName("show")).forEach(ul => {
        ul.classList.remove("show");
        if (ul.previousElementSibling) {
            ul.previousElementSibling.classList.remove("rotate");
        }
    });
}

// Mobile hamburger and overlay
const hamburgerBtn = document.createElement("button");
hamburgerBtn.id = "hamburger-btn";
hamburgerBtn.innerHTML = `<span></span><span></span><span></span>`;
document.body.appendChild(hamburgerBtn);

const overlay = document.createElement("div");
overlay.id = "overlay";
document.body.appendChild(overlay);

hamburgerBtn.addEventListener("click", () => {
    hamburgerBtn.classList.toggle("active");
    if (sidebar) {
        sidebar.classList.toggle("show");
    }
    overlay.classList.toggle("show");
});

overlay.addEventListener("click", () => {
    hamburgerBtn.classList.remove("active");
    if (sidebar) {
        sidebar.classList.remove("show");
    }
    overlay.classList.remove("show");
});

// Optional charts / timeline controls – only initialize if elements exist and Chart is available
if (typeof Chart !== "undefined") {
    const trendCanvas = document.getElementById('trendChart');
    if (trendCanvas) {
        const trendCtx = trendCanvas.getContext('2d');
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
    }

    const regionCanvas = document.getElementById('regionChart');
    if (regionCanvas) {
        const regionCtx = regionCanvas.getContext('2d');
        const regionGradient = regionCtx.createLinearGradient(0, 0, 0, regionCtx.canvas.height);
        regionGradient.addColorStop(0, '#2872CB');
        regionGradient.addColorStop(1, '#01277E');

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
    }
}

// Timeline dropdown
const timelineBtn = document.querySelector('.timeline-btn');
const timelineOptions = document.querySelector('.timeline-options');

if (timelineBtn && timelineOptions) {
    const timelineText = timelineBtn.querySelector('.timeline-text');

    timelineBtn.addEventListener('click', () => {
        timelineBtn.classList.toggle('active');
        timelineOptions.style.display = timelineOptions.style.display === 'block' ? 'none' : 'block';
    });

    timelineOptions.querySelectorAll('li').forEach(option => {
        option.addEventListener('click', () => {
            if (timelineText) {
                timelineText.textContent = option.textContent;
            }
            timelineBtn.classList.remove('active');
            timelineOptions.style.display = 'none';
        });
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.timeline-dropdown')) {
            timelineBtn.classList.remove('active');
            timelineOptions.style.display = 'none';
        }
    });
}



