const API_URL = 'http://127.0.0.1:8000';
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

let stream = null;
let scanning = false;
let capturing = false;
let capturedImages = [];

// Navigation
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-links li').forEach(l => l.classList.remove('active'));
    
    document.getElementById(pageId).classList.add('active');
    event.target.classList.add('active');

    if (pageId === 'scanner') {
        startCamera();
        scanning = true;
        processScanner();
    } else {
        scanning = false;
        if (pageId === 'dashboard') loadDashboard();
        if (pageId === 'users') loadUsers();
    }
}

// Camera controls
async function startCamera() {
    if (stream) return;
    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        video.onloadedmetadata = () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
        };
    } catch (err) {
        console.error("Webcam error:", err);
        alert("Could not access webcam.");
    }
}

// Scanning logic
async function processScanner() {
    if (!scanning) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Get frame as base64
    const imageData = canvas.toDataURL('image/jpeg', 0.5);
    
    try {
        const response = await fetch(`${API_URL}/recognize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData })
        });
        const data = await response.json();

        if (data.results) {
            data.results.forEach(res => {
                const [x, y, w, h] = res.box;
                
                // Draw box
                ctx.strokeStyle = '#6366f1';
                ctx.lineWidth = 3;
                ctx.strokeRect(x, y, w, h);
                
                // Draw label
                ctx.fillStyle = '#6366f1';
                ctx.fillRect(x, y - 30, w, 30);
                ctx.fillStyle = 'white';
                ctx.font = '16px Inter';
                ctx.fillText(`${res.name} (${res.confidence})`, x + 5, y - 10);

                if (res.name !== "Unknown") {
                    markAttendance(res.name);
                }
            });
        }
    } catch (err) {
        console.error("Scan error:", err);
    }

    setTimeout(processScanner, 100); // 10 FPS scan
}

async function markAttendance(name) {
    const formData = new FormData();
    formData.append('name', name);
    
    try {
        await fetch(`${API_URL}/mark_attendance`, {
            method: 'POST',
            body: formData
        });
    } catch (err) {
        console.error("Attendance mark error:", err);
    }
}

// Dashboard data
async function loadDashboard() {
    try {
        const statusRes = await fetch(`${API_URL}/status`);
        const status = await statusRes.json();
        document.getElementById('total-users').innerText = status.users_count;

        const attendRes = await fetch(`${API_URL}/attendance`);
        const attendance = await attendRes.json();
        document.getElementById('today-count').innerText = attendance.length;

        const tbody = document.getElementById('attendance-tbody');
        tbody.innerHTML = attendance.map(a => `
            <tr>
                <td>${a.name}</td>
                <td>${a.time}</td>
            </tr>
        `).join('');
    } catch (err) {
        console.error("Dashboard hit error:", err);
    }
}

// User management
async function loadUsers() {
    try {
        const res = await fetch(`${API_URL}/status`);
        const data = await res.json();
        const list = document.getElementById('registered-users-list');
        list.innerHTML = data.users.map(u => `
            <div class="user-item">
                <span>${u}</span>
                <button class="delete-user-btn" onclick="deleteUser('${u}')" title="Delete User">×</button>
            </div>
        `).join('');
    } catch (err) {
        console.error("User list error:", err);
    }
}

document.getElementById('start-capture-btn').onclick = async () => {
    const name = document.getElementById('new-user-name').value.trim();
    if (!name) return alert("Enter a name first!");

    await startCamera();
    capturing = true;
    capturedImages = [];
    const status = document.getElementById('capture-status');
    status.innerText = "Capturing... Stay still";

    const captureInterval = setInterval(() => {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        capturedImages.push(canvas.toDataURL('image/png'));
        status.innerText = `Captured ${capturedImages.length}/50`;

        if (capturedImages.length >= 50) {
            clearInterval(captureInterval);
            saveUser(name);
        }
    }, 100);
};

async function saveUser(name) {
    const status = document.getElementById('capture-status');
    status.innerText = "Saving and training model...";

    const formData = new FormData();
    formData.append('name', name);
    capturedImages.forEach(img => formData.append('images', img));

    try {
        await fetch(`${API_URL}/add_user`, {
            method: 'POST',
            body: formData
        });
        status.innerText = "User added successfully!";
        document.getElementById('new-user-name').value = '';
        loadUsers();
    } catch (err) {
        status.innerText = "Error saving user.";
        console.error("Save error:", err);
    }
}

// Data Management
async function clearLogs() {
    try {
        await fetch(`${API_URL}/logs`, { method: 'DELETE' });
        loadDashboard();
    } catch (err) {
        console.error("Clear logs error:", err);
    }
}

async function deleteUser(name) {
    try {
        await fetch(`${API_URL}/users/${encodeURIComponent(name)}`, { method: 'DELETE' });
        loadUsers();
        loadDashboard(); // update counts
    } catch (err) {
        console.error("Delete user error:", err);
    }
}


// Init
loadDashboard();
