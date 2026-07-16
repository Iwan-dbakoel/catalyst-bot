import os
import requests
import time

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "MASUKKAN_TOKEN_DISINI")
CHAT_ID = os.getenv("CHAT_ID", "MASUKKAN_ID_DISINI")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message}
    try: 
        requests.post(url, json=payload)
    except: 
        pass

if __name__ == "__main__":
    send_telegram_message("✅ Master Trader Bot V5.3 (Bare Minimum) Active. Server Railway sehat!")
    while True:
        print("Bot berjalan...")
        time.sleep(60)
