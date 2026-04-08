# Face Recognition Attendance System 📸

A simple and efficient face recognition system built with Python and OpenCV. This project can capture face data for multiple users and mark attendance automatically in a CSV file.

## Features
- **Interactive Data Capture**: Capture 100 face images per user with real-time feedback.
- **LBPH Face Recognition**: Uses Local Binary Patterns Histograms for robust recognition.
- **Smart Attendance**: Logs unique name and timestamp to `attendance.csv`.
- **Easy Initialization**: No manual code editing for adding new users.

## Prerequisites
- Python 3.x
- OpenCV with Contrib module

```bash
pip install opencv-contrib-python
```

## 🌐 Web Interface (New!)
The project now includes a premium web dashboard for a better user experience.

### 1. Install Web Dependencies
```bash
pip install fastapi uvicorn python-multipart
```

### 2. Start the Backend
```bash
python app.py
```

### 3. Open the Dashboard
Simply open `index.html` in your web browser (Chrome, Edge, etc.).

---

## 🚀 How to Use (Classic CLI)

### 1. Capture Face Data
Run the following command and enter your name:
```bash
python datacreate.py
```

### 2. Start Recognition
Run the recognizer to start marking attendance:
```bash
python atten.py
```
Press **ESC** to stop the camera and shutdown the system.

## Project Structure
- `app.py`: FastAPI backend for the web interface.
- `index.html`, `style.css`, `script.js`: Web frontend files.
- `datacreate.py`: CLI script to capture face data.
- `atten.py`: CLI recognition script.
- `haarcascade_frontalface_default.xml`: Pre-trained model for face detection.
- `datasets/`: Folder containing trained face images (auto-generated).
- `attendance.csv`: Log file (auto-generated).

---
Created by [sasank2006](https://github.com/sasank2006)
