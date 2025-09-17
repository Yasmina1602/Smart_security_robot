
from flask import Flask
from flask_sock import Sock 
import threading
from routes.index import index_bp
from routes.video import video_bp
from routes.control import control_bp, sock
from fire_detection import detection_and_alert_loop, camera_loop

app = Flask(__name__)
app.register_blueprint(index_bp)
app.register_blueprint(video_bp)
app.register_blueprint(control_bp)
sock.init_app(app)

if __name__ == '__main__':
    threading.Thread(target=camera_loop, daemon=True).start()        
    threading.Thread(target=detection_and_alert_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False, threaded=True)

