from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import cv2
import numpy as np
import os
import base64
from datetime import datetime
import json

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
DATASETS_DIR = 'datasets'
HAAR_FILE = 'haarcascade_frontalface_default.xml'
ATTENDANCE_FILE = 'attendance.csv'
(WIDTH, HEIGHT) = (130, 100)
CONFIDENCE_THRESHOLD = 80

# State
model = None
face_cascade = cv2.CascadeClassifier(HAAR_FILE)
names_map = {}

def load_recognizer():
    global model, names_map
    images, labels = [], []
    names_map = {}
    id_counter = 0

    if not os.path.exists(DATASETS_DIR):
        os.makedirs(DATASETS_DIR)

    for subdir in os.listdir(DATASETS_DIR):
        path = os.path.join(DATASETS_DIR, subdir)
        if not os.path.isdir(path): continue
        
        names_map[id_counter] = subdir
        for filename in os.listdir(path):
            img = cv2.imread(os.path.join(path, filename), 0)
            if img is not None:
                # Guarantee image size to prevent inhomogeneous shape crashes
                img = cv2.resize(img, (WIDTH, HEIGHT))
                images.append(img)
                labels.append(id_counter)
        id_counter += 1

    if images:
        model = cv2.face.LBPHFaceRecognizer_create()
        model.train(np.array(images), np.array(labels))
        return True
    return False

# Initial Load
load_recognizer()

class ProcessFrame(BaseModel):
    image: str # Base64 string

@app.get("/status")
async def get_status():
    return {
        "model_loaded": model is not None,
        "users_count": len(names_map),
        "users": list(names_map.values())
    }

@app.post("/recognize")
async def recognize(data: ProcessFrame):
    if model is None:
        return {"error": "Model not trained. Add users first."}

    # Decode Base64 image
    img_data = base64.b64decode(data.image.split(',')[1])
    nparr = np.frombuffer(img_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    results = []

    for (x, y, w, h) in faces:
        face = gray[y:y+h, x:x+w]
        face_resize = cv2.resize(face, (WIDTH, HEIGHT))
        
        prediction = model.predict(face_resize)
        
        if prediction[1] < CONFIDENCE_THRESHOLD:
            name = names_map[prediction[0]]
            results.append({
                "name": name,
                "confidence": round(prediction[1], 2),
                "box": [int(x), int(y), int(w), int(h)]
            })
        else:
            results.append({
                "name": "Unknown",
                "confidence": round(prediction[1], 2),
                "box": [int(x), int(y), int(w), int(h)]
            })
            
    return {"results": results}

@app.post("/mark_attendance")
async def mark_attendance(name: str = Form(...)):
    if name == "Unknown": return {"status": "ignored"}
    
    if not os.path.isfile(ATTENDANCE_FILE):
        with open(ATTENDANCE_FILE, 'w') as f:
            f.write('Name,DateTime\n')

    with open(ATTENDANCE_FILE, 'r+') as f:
        lines = f.readlines()
        names_logged = [line.split(',')[0].strip() for line in lines]
        
        if name not in names_logged:
            now = datetime.now()
            dt_string = now.strftime('%Y-%m-%d %H:%M:%S')
            if lines and not lines[-1].endswith('\n'):
                f.write('\n')
            f.write(f'{name},{dt_string}\n')
            return {"status": "marked", "name": name, "time": dt_string}
            
    return {"status": "already_marked"}

@app.get("/attendance")
async def get_attendance():
    if not os.path.exists(ATTENDANCE_FILE):
        return []
    
    logs = []
    with open(ATTENDANCE_FILE, 'r') as f:
        next(f) # skip header
        for line in f:
            if ',' in line:
                name, dt = line.strip().split(',')
                logs.append({"name": name, "time": dt})
    return logs[::-1] # return latest first

@app.post("/add_user")
async def add_user(name: str = Form(...), images: list[str] = Form(...)):
    user_path = os.path.join(DATASETS_DIR, name)
    if not os.path.exists(user_path):
        os.makedirs(user_path)
    
    saved_count = 0
    for img_b64 in images:
        img_data = base64.b64decode(img_b64.split(',')[1])
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect face in the captured frame
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            face = gray[y:y+h, x:x+w]
            face_resize = cv2.resize(face, (WIDTH, HEIGHT))
            cv2.imwrite(os.path.join(user_path, f"{saved_count+1}.png"), face_resize)
            saved_count += 1
            break # Save only one face per frame
            
    # Retrain model
    load_recognizer()
    return {"status": "user_added", "username": name, "faces_detected": saved_count}

@app.delete("/logs")
async def clear_logs():
    if os.path.exists(ATTENDANCE_FILE):
        with open(ATTENDANCE_FILE, 'w') as f:
            f.write('Name,DateTime\n')
    return {"status": "logs_cleared"}

@app.delete("/users/{name}")
async def delete_user(name: str):
    user_path = os.path.join(DATASETS_DIR, name)
    if not os.path.exists(user_path):
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove directory and all its files
    import shutil
    shutil.rmtree(user_path)
    
    # Reload recognizer to update model and names_map
    load_recognizer()
    return {"status": "user_deleted", "name": name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
