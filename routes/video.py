
from flask import Blueprint, Response
from fire_detection import video_stream 

video_bp = Blueprint('video', __name__)

@video_bp.route('/video_feed')
def video_feed():
    headers = {'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'}
    return Response(video_stream(), 
    mimetype='multipart/x-mixed-replace; boundary=frame')