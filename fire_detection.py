import numpy as np
import cv2
import threading
import websocket
import time
import config
import requests 
import supervision as sv
from telegram import Bot
from ultralytics import YOLO
from supervision.draw.color import Color
from supervision.annotators.core import LabelAnnotator


output_frame = None
frame_lock = threading.Lock() 

ESP32_WEBSOCKET_URL = "ws://192.168.4.1/ws"  
ws_connection = None

CLASS_COLORS = {
    'Fire': Color.RED,
    'Smoke': Color.BLACK,
}
bounding_box_annotator = sv.BoxAnnotator()
top_center_label_annotator = LabelAnnotator(
    text_scale=0.5, text_thickness=1, text_color=Color.BLACK, text_padding=5, text_position=sv.Position.TOP_CENTER
)

def camera_loop(camera_index=0):
    global output_frame, frame_lock
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("Kamerani ochib bo'lmadi!")
        return
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Kameradan kadr olinmadi.")
            break

        with frame_lock:
            output_frame = frame.copy()

        # print("🎥 Kadr yangilandi")

        time.sleep(0.03)  # ~30 FPS

    cap.release()

def load_model(model_path): 
    return YOLO(model_path)

def setup_tracking(fps): 
    return sv.ByteTrack(frame_rate=fps)

def check_fire_smoke_present(detections, model):
    fire_detected = 0
    smoke_detected = 0
    for class_id in detections.class_id:
        class_name = model.model.names.get(int(class_id), "").lower()

        if "fire" in class_name: 
            fire_detected = 1
        elif "smoke" in class_name: 
            smoke_detected = 1
    any_detection = 1 if (fire_detected or smoke_detected) else 0
    return {'fire_detected': fire_detected, 'smoke_detected': smoke_detected, 'any_detection': any_detection}

def annotate_frame(frame, model, detections):
    annotated_frame = frame.copy()
    
    for i, (xyxy, tracker_id, class_id) in enumerate(zip(detections.xyxy, detections.tracker_id, detections.class_id)):
        x1, y1, x2, y2 = map(int, xyxy)
        class_id_int = int(class_id)
       
        class_name = model.model.names.get(class_id_int, f"ID:{class_id_int}")
        print(f"Detected: {class_name} with Tracker ID: {tracker_id}")

        color = CLASS_COLORS.get(class_name, Color.RED)
        print(f"Using color: {color} for class: {class_name}")
        detection_box = sv.Detections(
            xyxy=np.array([[x1, y1, x2, y2]]),
            confidence=np.array([1.0]), 
            class_id=np.array([class_id_int]),
            tracker_id=np.array([tracker_id])
        )
        detection_box.color = [color]
        annotated_frame = bounding_box_annotator.annotate(
            scene=annotated_frame,
            detections=detection_box
        )
    if len(detections) > 0:
        labels = [
            f"{model.model.names.get(int(class_id), f'ID:{int(class_id)}')} ID:{tracker_id}"
            for class_id, tracker_id in zip(detections.class_id, detections.tracker_id)
        ]
        annotated_frame = top_center_label_annotator.annotate(
            scene=annotated_frame, 
            detections=detections, 
            labels=labels
        )

    return annotated_frame

def connect_to_esp32():
    global ws_connection
    while True:
        try:
            print("ESP32 ga ulanishga harakat qilinmoqda...")
            ws_connection = websocket.create_connection(ESP32_WEBSOCKET_URL)
            print("ESP32 ga WebSocket orqali muvaffaqiyatli ulanildi!")
            ws_connection.send("python_client_connected") 
            break 
        except Exception as e:
            print(f"ESP32 ga ulanib bo'lmadi: {e}. 5 soniyadan so'ng qayta urinish.")
            ws_connection = None
            time.sleep(5)

def send_to_esp32(message):
    global ws_connection
    if ws_connection and ws_connection.connected:
        try:
            ws_connection.send(message)
        except Exception as e:
            print(f"ESP32 ga yuborishda xato: {e}")
            ws_connection = None
            threading.Thread(target=connect_to_esp32, daemon=True).start()
    elif not ws_connection:
        print("ESP32 bilan aloqa yo'q. Qayta ulanishga harakat qilinmoqda...")
        threading.Thread(target=connect_to_esp32, daemon=True).start()

def send_telegram_photo(frame):
    url = f"https://api.telegram.org/bot{config.get_token()}/sendPhoto"
    _, img_encoded = cv2.imencode('.jpg', frame)
    files = {'photo': ('fire.jpg', img_encoded.tobytes())}
    data = {'chat_id': config.get_chat_id(), 'caption': 'Olov aniqlandi!'}
    try:
        requests.post(url, files=files, data=data, timeout=5)
    except Exception as e:
        print(f"Telegramga rasm yuborishda xato: {e}")

def detection_and_alert_loop():
    global output_frame, frame_lock

    MODEL_PATH = "models/building_models35k.pt"
    CONFIDENCE_THRESHOLD = 0.5
    NMS_IOU_THRESHOLD = 0.4

    model = load_model(MODEL_PATH)
    tracker = setup_tracking(30)
    
    last_alert_time = 0
    alert_cooldown = 10 

    print("Olovni aniqlash sikli ishga tushdi...")
    while True:
        with frame_lock:
            if output_frame is None:
                time.sleep(0.1)
                continue
            frame = output_frame.copy()
            
        result = model(frame, imgsz=320, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(result)
        detections = detections[detections.confidence > CONFIDENCE_THRESHOLD]
        detections = detections[np.isin(detections.class_id.astype(int), [6, 7])]
        detections = tracker.update_with_detections(detections)
        
        if len(detections) > 0:
            current_time = time.time()
            if current_time - last_alert_time > alert_cooldown:
                print("🔥 OLOV ANIQLANDI → ESP32 + Telegram buyruq yuborilmoqda \n")
                send_to_esp32("fire_alert") 
                send_telegram_photo(frame) 
                last_alert_time = current_time

        time.sleep(0.05)

def video_stream():
    global output_frame, frame_lock
    while True:
        with frame_lock:
            if output_frame is None:
                time.sleep(0.1) 
                continue
            
            ret, frame_buf = cv2.imencode('.jpg', output_frame)
        
        if not ret:
            continue

        frame = frame_buf.tobytes()
        # print("📤 Kadr brauzerga yuborildi")

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        