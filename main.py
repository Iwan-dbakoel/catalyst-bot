import yfinance as yf
import pandas as pd
import requests
import time
import os
from datetime import datetime
import pytz

# === KONFIGURASI TELEGRAM & ROBOT ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "MASUKKAN_TOKEN_DISINI")
CHAT_ID = os.getenv("CHAT_ID", "MASUKKAN_ID_DISINI")

WATCHLIST = ['NVDA', 'TSLA', 'AAPL', 'AMZN', 'AMD', 'META', 'MSFT', 'PLTR', 'LCID', 'SOFI']

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending telegram: {e}")

def scan_catalyst():
    est = pytz.timezone('US/Eastern')
    now_est = datetime.now(est)
    
    if not (9 <= now_est.hour <= 15):
        return

    print(f"[{now_est.strftime('%H:%M:%S')}] Memindai pasar AS...")
    alerts = []

    for ticker in WATCHLIST:
        try:
            data = yf.download(ticker, period='1d', interval='5m', progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            if len(data) < 10:
                continue

            avg_vol = data['Volume'].iloc[:-1].mean()
            current_vol = data['Volume'].iloc[-1]
            current_price = data['Close'].iloc[-1]
            prev_close = data['Close'].iloc[-2]

            if avg_vol > 0 and current_vol > (3 * avg_vol):
                price_change_pct = ((current_price - prev_close) / prev_close) * 100
                if price_change_pct > 1.0:
                    alert_msg = (
                        f"🚀 <b>SINYAL CATALYST DETECTED</b> 🚀\n"
                        f"Ticker: <b>{ticker}</b>\n"
                        f"Price: ${current_price:.2f}\n"
                        f"Spike: +{price_change_pct:.2f}% (5m)\n"
                        f"Volume: {current_vol/1000:.0f}K (3x Normal)\n"
                        f"Action: Watch for ORB Breakout!"
                    )
                    alerts.append(alert_msg)
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")

    if alerts:
        for alert in alerts:
            send_telegram_message(alert)
            time.sleep(1)

if __name__ == "__main__":
    send_telegram_message("✅ <b>Master Trader Bot Active.</b>\nMemindai Smart Money Volume di Bursa US...")
    while True:
        scan_catalyst()
        print("Menunggu 15 menit untuk scan berikutnya...\n")
        time.sleep(900)
