
import time
from fire_detection import output_frame, frame_lock
import cv2

def main():
    while True:
        with frame_lock:
            if output_frame is None:
                time.sleep(0.1)
                continue
            frame = output_frame.copy()

        # bu yerdan rasmni TG botga yuborish mumkin
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')