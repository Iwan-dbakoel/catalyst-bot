import os
import requests
import time

# === KONFIGURASI ===
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cyaehynqfynggtvhcvkg.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "MASUKKAN_SERVICE_ROLE_DISINI")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "MASUKKAN_TOKEN_DISINI")
CHAT_ID = os.getenv("CHAT_ID", "MASUKKAN_ID_DISINI")

# === FUNGSI TELEGRAM ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try: 
        requests.post(url, json=payload)
    except: 
        pass

# === CEK KONEKSI SUPABASE ===
db_status = "Gagal menemukan library Supabase."
try:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Coba melakukan query sederhana ke database
    supabase.table('active_signals').select('*').limit(1).execute()
    db_status = "Sukses! Koneksi Supabase terbukti berfungsi."
except Exception as e:
    db_status = f"Gagal koneksi Supabase: {e}"

# === JALANKAN ROBOT (TANPA FASTAPI) ===
if __name__ == "__main__":
    # 1. Kirim laporan status ke Telegram
    send_telegram_message(f"✅ <b>Master Trader Bot V5.2 (Debug Mode) Active.</b>\n\nDB Status: {db_status}")
    
    # 2. Buat loop sederhana agar server tidak mati
    while True:
        print("Bot berjalan...")
        time.sleep(60)
