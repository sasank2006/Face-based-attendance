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
        if (pageId === 'timetable') loadTimetable();
        if (pageId === 'attendance') loadDashboard(); // Reuse for both
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
        if (tbody) {
            tbody.innerHTML = attendance.slice(0, 5).map(a => `
                <tr>
                    <td>${a.name}</td>
                    <td>${a.subject || 'General'}</td>
                    <td>${a.time}</td>
                </tr>
            `).join('');
        }
        
        const fullTbody = document.getElementById('full-attendance-tbody');
        if (fullTbody) {
            fullTbody.innerHTML = attendance.map(a => `
                <tr>
                    <td>${a.name}</td>
                    <td>${a.subject || 'General'}</td>
                    <td>${a.time}</td>
                </tr>
            `).join('');
        }
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


// Timetable logic
let selectedTimetableUsers = new Set();

function toggleTimetableUser(user, elt) {
    if (selectedTimetableUsers.has(user)) {
        selectedTimetableUsers.delete(user);
        elt.classList.remove('selected');
    } else {
        selectedTimetableUsers.add(user);
        elt.classList.add('selected');
    }
}

async function loadTimetable() {
    try {
        const res = await fetch(`${API_URL}/timetable`);
        const data = await res.json();
        const list = document.getElementById('timetable-list');
        list.innerHTML = data.map(t => `
            <tr>
                <td>${t.subject}</td>
                <td>${t.start_time} - ${t.end_time}</td>
                <td>${(t.enrolled_users && t.enrolled_users.length > 0) ? t.enrolled_users.map(u => `<span style="background:var(--primary);color:white;padding:0.2rem 0.5rem;border-radius:10px;font-size:0.7rem;margin-right:0.3rem;">${u}</span>`).join('') : '<span style="color:var(--text-muted);font-size:0.8rem;">All Active</span>'}</td>
                <td><button class="btn btn-danger" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;" onclick="deleteTimetableSlot(${t.id})">Delete</button></td>
            </tr>
        `).join('');

        const userRes = await fetch(`${API_URL}/status`);
        const userData = await userRes.json();
        selectedTimetableUsers.clear();
        
        const selector = document.getElementById('timetable-student-selector');
        if (selector && userData.users) {
            selector.innerHTML = userData.users.map(u => `
                <div class="user-pill" onclick="toggleTimetableUser('${u}', this)">${u}</div>
            `).join('');
            if (userData.users.length === 0) {
                 selector.innerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">No users registered yet.</span>';
            }
        }
    } catch (err) {
        console.error("Timetable load error:", err);
    }
}

async function addTimetableSlot() {
    const subject = document.getElementById('subject-name').value.trim();
    const start = document.getElementById('start-time').value;
    const end = document.getElementById('end-time').value;
    const status = document.getElementById('timetable-status');

    if (!subject || !start || !end) {
        status.innerText = "Please fill in all fields.";
        return;
    }
    
    if (start >= end) {
        status.innerText = "Start time must be before end time.";
        return;
    }

    try {
        await fetch(`${API_URL}/timetable`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                subject: subject, 
                start_time: start, 
                end_time: end,
                enrolled_users: Array.from(selectedTimetableUsers)
            })
        });
        status.innerText = "Slot added successfully!";
        document.getElementById('subject-name').value = '';
        document.getElementById('start-time').value = '';
        document.getElementById('end-time').value = '';
        loadTimetable();
        
        setTimeout(() => status.innerText = '', 3000);
    } catch (err) {
        status.innerText = "Error adding slot.";
        console.error("Add slot error:", err);
    }
}

async function deleteTimetableSlot(id) {
    try {
        await fetch(`${API_URL}/timetable/${id}`, { method: 'DELETE' });
        loadTimetable();
    } catch (err) {
        console.error("Delete slot error:", err);
    }
}

// Mock Time Logic
async function setMockTime() {
    const time = document.getElementById('mock-time-input').value;
    if (!time) return;
    try {
        await fetch(`${API_URL}/mock_time`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ time: time })
        });
        document.getElementById('mock-status').innerText = 'Mock active: ' + time;
    } catch(err) { console.error(err); }
}

async function clearMockTime() {
    try {
        await fetch(`${API_URL}/mock_time`, { method: 'DELETE' });
        document.getElementById('mock-time-input').value = '';
        document.getElementById('mock-status').innerText = 'Real time active';
        setTimeout(() => document.getElementById('mock-status').innerText = '', 2000);
    } catch(err) { console.error(err); }
}

// Init
loadDashboard();
