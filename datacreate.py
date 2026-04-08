import cv2
import os
import sys

# Path to Haar Cascade XML file
haar_file = 'haarcascade_frontalface_default.xml'
datasets = 'datasets'

# Check if Haar Cascade file exists
if not os.path.isfile(haar_file):
    print(f"Error: '{haar_file}' not found. Please ensure it is in the same directory.")
    sys.exit()

# Ask for the person's name
sub_data = input("Enter the name of the person: ").strip()
if not sub_data:
    print("Name cannot be empty.")
    sys.exit()

path = os.path.join(datasets, sub_data)
if not os.path.exists(path):
    os.makedirs(path)

# Image size
(width, height) = (130, 100)

face_cascade = cv2.CascadeClassifier(haar_file)
webcam = cv2.VideoCapture(0)

if not webcam.isOpened():
    print("Error: Could not access the webcam.")
    sys.exit()

print(f"Starting capture for '{sub_data}'. Please look at the camera.")
count = 1
while count <= 100:
    (_, im) = webcam.read()
    if im is None:
        break
    
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 4)
    
    for (x, y, w, h) in faces:
        cv2.rectangle(im, (x, y), (x + w, y + h), (255, 0, 0), 2)
        face = gray[y:y + h, x:x + w]
        face_resize = cv2.resize(face, (width, height))
        cv2.imwrite(f'{path}/{count}.png', face_resize)
        count += 1
        
    cv2.putText(im, f"Captured: {count-1}/100", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow('Face Data Capture', im)
    
    if cv2.waitKey(10) == 27: # ESC
        break

print(f"\nSuccessfully captured 100 images for {sub_data}!")
webcam.release()
cv2.destroyAllWindows()
