from flask import Blueprint
from flask_sock import Sock, ConnectionClosed
import websocket
import requests
import config

control_bp = Blueprint('control', __name__)
sock = Sock()

ESP32_WS_URL = "ws://192.168.4.1/ws"  # ESP32 IP manzilini moslang

def send_to_esp32(cmd):
    try:
        ws = websocket.create_connection(ESP32_WS_URL, timeout=2)
        ws.send(cmd)
        response = ws.recv()
        ws.close()
        return response
    except Exception as e:
        return f"ESP32 ulanib bo'lmadi: {e}"

def send_telegram_alert(msg):
    url = f"https://api.telegram.org/bot{config.get_token()}/sendMessage"
    try:
        requests.post(url, data={'chat_id': config.get_chat_id(), 'text': msg}, timeout=2)
    except Exception as e:
        print("Telegramga yuborib bo'lmadi:", e)

@sock.route('/ws')
def ws_control(ws):
    while True:
        try:
            cmd = ws.receive()
            if not cmd:
                break
            # Masalan, xavfli buyruq bo'lsa Telegramga xabar
            if cmd == "fire_alert" or cmd == "intruder_alert":
                send_telegram_alert(f"Xavf: {cmd}")
            response = send_to_esp32(cmd)
            ws.send(response)
        except ConnectionClosed:
            break