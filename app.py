from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import cv2
import numpy as np
import os
import base64
from datetime import datetime
import json
import asyncio

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
TIMETABLE_FILE = 'timetable.json'
PERFORMANCE_FILE = 'performance.json'
(WIDTH, HEIGHT) = (130, 100)
CONFIDENCE_THRESHOLD = 80

# State memory for absent tracking
processed_absent_slots = set()

async def auto_absent_loop():
    while True:
        await asyncio.sleep(10)
        now_dt = get_now()
        date_str = now_dt.strftime('%Y-%m-%d')
        current_time = now_dt.strftime('%H:%M')
        
        slots = []
        if os.path.exists(TIMETABLE_FILE):
            with open(TIMETABLE_FILE, 'r') as f:
                try: slots = json.load(f)
                except: pass
                
        if not slots: continue
        
        for s in slots:
            slot_key = f"{date_str}-{s.get('id')}"
            if slot_key in processed_absent_slots: continue
            
            end_t = s['end_time']
            if current_time > end_t:
                enrolled = s.get('enrolled_users', [])
                if not enrolled:
                    processed_absent_slots.add(slot_key)
                    continue
                    
                presents = set()
                if os.path.exists(ATTENDANCE_FILE):
                    with open(ATTENDANCE_FILE, 'r') as f:
                        next(f, None)
                        for line in f:
                            p = line.strip().split(',')
                            if len(p) >= 4:
                                n, sub, dt, status = p[0].strip(), p[1].strip(), p[2].strip(), p[3].strip()
                                if sub == s['subject'] and dt.startswith(date_str) and status == "Present":
                                    presents.add(n)
                                    
                absents = [u for u in enrolled if u not in presents]
                
                if absents:
                    mode = 'a' if os.path.exists(ATTENDANCE_FILE) else 'w'
                    with open(ATTENDANCE_FILE, mode) as f:
                        if mode == 'w': f.write('Name,Subject,DateTime,Status\n')
                        for a in absents:
                            dt_str = f"{date_str} {end_t}:00"
                            f.write(f"{a},{s['subject']},{dt_str},Absent\n")
                            
                processed_absent_slots.add(slot_key)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(auto_absent_loop())

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

MOCK_TIME = None

class MockTimeData(BaseModel):
    time: str

@app.post("/mock_time")
async def set_mock_time(data: MockTimeData):
    global MOCK_TIME
    MOCK_TIME = data.time
    return {"status": "mock_time_set", "time": MOCK_TIME}

@app.delete("/mock_time")
async def clear_mock_time():
    global MOCK_TIME
    MOCK_TIME = None
    return {"status": "mock_time_cleared"}

def get_now():
    now = datetime.now()
    if MOCK_TIME:
        try:
            h, m = map(int, MOCK_TIME.split(':'))
            now = now.replace(hour=h, minute=m, second=0, microsecond=0)
        except:
            pass
    return now

def get_current_subject(name: str):
    if not os.path.isfile(TIMETABLE_FILE):
        return "General"
    with open(TIMETABLE_FILE, 'r') as f:
        try:
            timetable = json.load(f)
        except:
            timetable = []
            
    current_time = get_now().strftime('%H:%M')
    
    best_slot = None
    min_duration = 24 * 60 # max minutes in a day
    enrolled_list = []
    
    for slot in timetable:
        st_h, st_m = map(int, slot['start_time'].split(':'))
        en_h, en_m = map(int, slot['end_time'].split(':'))
        
        if slot['start_time'] <= current_time <= slot['end_time']:
            duration = (en_h * 60 + en_m) - (st_h * 60 + st_m)
            if duration < min_duration:
                min_duration = duration
                best_slot = slot['subject']
                enrolled_list = slot.get('enrolled_users', [])
                
    if best_slot:
        if len(enrolled_list) > 0 and name not in enrolled_list:
            return "General" # Fallback to Campus presence
        return best_slot
    return "General"

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
    
    subject = get_current_subject(name)

    if not os.path.isfile(ATTENDANCE_FILE):
        with open(ATTENDANCE_FILE, 'w') as f:
            f.write('Name,Subject,DateTime,Status\n')

    now_dt = get_now()
    dt_string = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    date_string = now_dt.strftime('%Y-%m-%d')

    with open(ATTENDANCE_FILE, 'r+') as f:
        lines = f.readlines()
        
        already_logged = False
        if len(lines) > 1:
            for line in lines[1:]:
                parts = line.split(',')
                if len(parts) >= 4:
                    log_name, log_subject, log_datetime, log_status = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
                    if log_name == name and log_subject == subject and log_datetime.startswith(date_string) and log_status == "Present":
                        already_logged = True
                        break
        
        if not already_logged:
            if lines and not lines[-1].endswith('\n'):
                f.write('\n')
            f.write(f'{name},{subject},{dt_string},Present\n')
            return {"status": "marked", "name": name, "subject": subject, "time": dt_string}
    return {"status": "already_marked"}

@app.get("/attendance")
async def get_attendance():
    if not os.path.exists(ATTENDANCE_FILE):
        return []
    
    logs = []
    with open(ATTENDANCE_FILE, 'r') as f:
        next(f, None) # skip header safely
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 3:
                logs.append({"name": parts[0], "subject": parts[1], "time": parts[2]})
            elif len(parts) == 2:
                # Handle old logs
                logs.append({"name": parts[0], "subject": "General", "time": parts[1]})
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
            f.write('Name,Subject,DateTime\n')
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

class TimetableSlot(BaseModel):
    subject: str
    start_time: str
    end_time: str
    enrolled_users: list[str] = []

@app.get("/timetable")
async def get_timetable():
    if not os.path.isfile(TIMETABLE_FILE):
        return []
    with open(TIMETABLE_FILE, 'r') as f:
        try:
            return json.load(f)
        except:
            return []

@app.post("/timetable")
async def add_timetable(slot: TimetableSlot):
    slots = await get_timetable()
    new_slot = slot.dict()
    new_slot["id"] = int(datetime.now().timestamp()) # Unique ID
    slots.append(new_slot)
    
    with open(TIMETABLE_FILE, 'w') as f:
        json.dump(slots, f, indent=4)
    return {"status": "added", "slot": new_slot}

@app.delete("/timetable/{slot_id}")
async def delete_timetable(slot_id: int):
    slots = await get_timetable()
    slots = [s for s in slots if s.get("id") != slot_id]
    
    with open(TIMETABLE_FILE, 'w') as f:
        json.dump(slots, f, indent=4)
    return {"status": "deleted"}

@app.put("/timetable/{slot_id}")
async def edit_timetable(slot_id: int, slot_data: TimetableSlot):
    slots = []
    if os.path.exists(TIMETABLE_FILE):
        with open(TIMETABLE_FILE, 'r') as f:
            try: slots = json.load(f)
            except: pass
            
    for s in slots:
        if s.get('id') == slot_id:
            s['subject'] = slot_data.subject
            s['start_time'] = slot_data.start_time
            s['end_time'] = slot_data.end_time
            s['enrolled_users'] = slot_data.enrolled_users
            break
            
    with open(TIMETABLE_FILE, 'w') as f:
        json.dump(slots, f, indent=4)
        
    return {"status": "success"}

class PerformanceData(BaseModel):
    name: str
    score: float

@app.post("/performance")
async def update_performance(data: PerformanceData):
    perf_data = {}
    if os.path.exists(PERFORMANCE_FILE):
        with open(PERFORMANCE_FILE, 'r') as f:
            try: perf_data = json.load(f)
            except: pass
    
    perf_data[data.name] = data.score
    
    with open(PERFORMANCE_FILE, 'w') as f:
        json.dump(perf_data, f)
        
    return {"status": "success"}

@app.get("/analytics")
async def get_analytics():
    perf_data = {}
    if os.path.exists(PERFORMANCE_FILE):
        with open(PERFORMANCE_FILE, 'r') as f:
            try: perf_data = json.load(f)
            except: pass
            
    attendance_counts = {}
    if os.path.exists(ATTENDANCE_FILE):
        with open(ATTENDANCE_FILE, 'r') as f:
            next(f, None)
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 4:
                    name = parts[0].strip()
                    subject = parts[1].strip()
                    status = parts[3].strip()
                    if subject not in ["General", "Campus"] and status == "Present":
                        attendance_counts[name] = attendance_counts.get(name, 0) + 1
                        
    # Ensure distinct user mapping
    all_users = set(names_map.values())
    analytics = []
    max_att = max(attendance_counts.values()) if attendance_counts else 1
    if max_att == 0: max_att = 1
    
    for u in all_users:
        cgpa = float(perf_data.get(u, 0.0))
        att_c = attendance_counts.get(u, 0)
        att_perc = (att_c / max_att) * 100
        cgpa_perc = (cgpa / 10.0) * 100
        
        analytics.append({
            "name": u,
            "attendance_count": att_c,
            "attendance_perc": round(att_perc),
            "performance_score": round(cgpa_perc),
            "cgpa": round(cgpa, 2)
        })
        
    return analytics

@app.get("/students")
async def get_students():
    all_names = list(set(names_map.values()))
    perf_data = {}
    if os.path.exists(PERFORMANCE_FILE):
        with open(PERFORMANCE_FILE, 'r') as f:
            try: perf_data = json.load(f)
            except: pass
            
    slots = []
    if os.path.exists(TIMETABLE_FILE):
        with open(TIMETABLE_FILE, 'r') as f:
            try: slots = json.load(f)
            except: pass
            
    result = []
    for n in all_names:
        enrolled_slots = [s['id'] for s in slots if n in s.get('enrolled_users', [])]
        result.append({
            "name": n,
            "cgpa": float(perf_data.get(n, 0.0)),
            "enrolled_slots": enrolled_slots
        })
    return result

class SetStudentClasses(BaseModel):
    slot_ids: list[int]

@app.post("/student/{name}/classes")
async def set_student_classes(name: str, data: SetStudentClasses):
    slots = []
    if os.path.exists(TIMETABLE_FILE):
        with open(TIMETABLE_FILE, 'r') as f:
            try: slots = json.load(f)
            except: pass
            
    for s in slots:
        users = set(s.get('enrolled_users', []))
        if s.get('id') in data.slot_ids:
            users.add(name)
        else:
            users.discard(name)
        s['enrolled_users'] = list(users)
        
    with open(TIMETABLE_FILE, 'w') as f:
        json.dump(slots, f, indent=4)
        
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
