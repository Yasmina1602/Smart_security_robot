import os
from dotenv import load_dotenv

load_dotenv()

def get_token():
    return os.getenv("TELEGRAM_BOT_TOKEN")

def get_chat_id():
    return os.getenv("TELEGRAM_CHAT_ID")
