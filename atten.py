import cv2
import numpy as np
import os
import sys
from datetime import datetime

# Paths and Config
datasets = 'datasets'
haar_file = 'haarcascade_frontalface_default.xml'
(width, height) = (130, 100)
CONFIDENCE_THRESHOLD = 80 # Lower is more strict (LBPH distance)

# Load Haar Cascade
if not os.path.isfile(haar_file):
    print(f"Error: {haar_file} not found.")
    sys.exit()
face_cascade = cv2.CascadeClassifier(haar_file)

# Initialize data
(images, labels, names) = ([], [], {})
id_counter = 0

# Load Datasets
print("Loading face data...")
if not os.path.isdir(datasets):
    print("Error: 'datasets' folder not found. Please run datacreate.py first.")
    sys.exit()

for subdir in os.listdir(datasets):
    path = os.path.join(datasets, subdir)
    if not os.path.isdir(path):
        continue
    
    # Map ID to Name
    names[id_counter] = subdir
    print(f" - Loading data for {subdir}")
    
    for filename in os.listdir(path):
        img_path = os.path.join(path, filename)
        img = cv2.imread(img_path, 0) # Grayscale
        if img is not None:
            images.append(img)
            labels.append(id_counter)
    id_counter += 1

if not images:
    print("Error: No images found. Capture some faces using datacreate.py first.")
    sys.exit()

# Train Model
print("Training recognizer...")
try:
    model = cv2.face.LBPHFaceRecognizer_create()
    model.train(np.array(images), np.array(labels))
except Exception as e:
    print(f"Error: {e}")
    print("Make sure 'opencv-contrib-python' is installed.")
    sys.exit()

def mark_attendance(name):
    # Check if header exists
    file_path = 'attendance.csv'
    if not os.path.isfile(file_path):
        with open(file_path, 'w') as f:
            f.write('Name,DateTime\n')

    with open(file_path, 'r+') as f:
        existing_lines = f.readlines()
        names_logged = [line.split(',')[0].strip() for line in existing_lines]
        
        if name not in names_logged:
            now = datetime.now()
            dt_string = now.strftime('%Y-%m-%d %H:%M:%S')
            # Ensure file ends with newline before appending
            if existing_lines and not existing_lines[-1].endswith('\n'):
                f.write('\n')
            f.write(f'{name},{dt_string}\n')
            print(f"Attendance marked for: {name}")

# Recognition Loop
webcam = cv2.VideoCapture(0)
if not webcam.isOpened():
    print("Error: Could not access webcam.")
    sys.exit()

print("\nSystem Online. Press ESC to quit.")
while True:
    (_, im) = webcam.read()
    if im is None:
        break
        
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    for (x, y, w, h) in faces:
        face = gray[y:y+h, x:x+w]
        face_resize = cv2.resize(face, (width, height))
        
        # Predict
        prediction = model.predict(face_resize)
        
        # prediction[1] is the distance (confidence)
        # For LBPH, lower distance means better match
        if prediction[1] < CONFIDENCE_THRESHOLD:
            name = names[prediction[0]]
            label_text = f"{name} ({prediction[1]:.0f})"
            color = (0, 255, 0)
            mark_attendance(name)
        else:
            label_text = "Unknown"
            color = (0, 0, 255)
            
        cv2.rectangle(im, (x, y), (x+w, y+h), color, 2)
        cv2.putText(im, label_text, (x, y-10), 
                    cv2.FONT_HERSHEY_PLAIN, 1, color, 2)
                    
    cv2.imshow('Face Recognition System', im)
    if cv2.waitKey(10) == 27:
        break

webcam.release()
cv2.destroyAllWindows()
print("\nSystem Shutdown.")
