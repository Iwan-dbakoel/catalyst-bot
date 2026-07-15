import yfinance as yf
import pandas as pd
import requests
import time
import os
import sqlite3
from datetime import datetime
import pytz

# === KONFIGURASI TELEGRAM & ROBOT ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "MASUKKAN_TOKEN_DISINI")
CHAT_ID = os.getenv("CHAT_ID", "MASUKKAN_ID_DISINI")
WATCHLIST = ['NVDA', 'TSLA', 'AAPL', 'AMZN', 'AMD', 'META', 'MSFT', 'PLTR', 'LCID', 'SOFI']

# === SETUP DATABASE LOKAL (MEMORY SERVER) ===
def init_db():
    conn = sqlite3.connect('trading_memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS active_signals
                 (ticker TEXT PRIMARY KEY, entry_price REAL, entry_time TEXT)''')
    conn.commit()
    conn.close()

def save_signal(ticker, price):
    conn = sqlite3.connect('trading_memory.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO active_signals VALUES (?, ?, ?)", 
              (ticker, price, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def remove_signal(ticker):
    conn = sqlite3.connect('trading_memory.db')
    c = conn.cursor()
    c.execute("DELETE FROM active_signals WHERE ticker=?", (ticker,))
    conn.commit()
    conn.close()

def get_active_signals():
    conn = sqlite3.connect('trading_memory.db')
    c = conn.cursor()
    c.execute("SELECT * FROM active_signals")
    rows = c.fetchall()
    conn.close()
    return rows

# === FUNGSI TELEGRAM ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending telegram: {e}")

# === OTAK ROBOT: SCAN & TRACKING ===
def scan_and_track():
    est = pytz.timezone('US/Eastern')
    now_est = datetime.now(est)
    
    # Cek jika pasar AS buka (09:00 - 16:00 EST)
    if not (9 <= now_est.hour <= 15):
        return

    print(f"[{now_est.strftime('%H:%M:%S')}] Memindai pasar & Mengecek posisi...")
    
    # 1. CEK POSISI YANG SUDAH ADA (TRACKING PROFIT/LOSS)
    active_trades = get_active_signals()
    for trade in active_trades:
        ticker = trade[0]
        entry_price = trade[1]
        try:
            data = yf.download(ticker, period='1d', interval='5m', progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            if len(data) > 0:
                current_price = data['Close'].iloc[-1]
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                
                # Jika Profit mencapai 5% atau lebih
                if pnl_pct >= 5.0:
                    msg = f"✅ <b>WIN TRACKED!</b>\nTicker: <b>{ticker}</b>\nEntry: ${entry_price:.2f}\nCurrent: ${current_price:.2f}\nProfit: +{pnl_pct:.2f}%"
                    send_telegram_message(msg)
                    remove_signal(ticker) # Hapus dari radar karena sukses
                    
                # Jika Loss mencapai -3% atau lebih
                elif pnl_pct <= -3.0:
                    msg = f"❌ <b>LOSS TRACKED!</b>\nTicker: <b>{ticker}</b>\nEntry: ${entry_price:.2f}\nCurrent: ${current_price:.2f}\nLoss: {pnl_pct:.2f}%"
                    send_telegram_message(msg)
                    remove_signal(ticker) # Hapus dari radar karena kena stop loss
        except Exception as e:
            print(f"Error tracking {ticker}: {e}")

    # 2. CARI SAHAM BARU (CATALYST DETECTION)
    for ticker in WATCHLIST:
        # Skip saham yang sudah ada di radar
        if any(trade[0] == ticker for trade in active_trades):
            continue
            
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
                    send_telegram_message(alert_msg)
                    save_signal(ticker, current_price) # Simpan ke memory robot
                    
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")

if __name__ == "__main__":
    init_db() # Jalankan database saat pertama kali bot nyala
    send_telegram_message("✅ <b>Master Trader Bot V2 Active.</b>\nMesin Auto-Tracking Profit/Loss telah diaktifkan. Memindai Bursa US...")
    while True:
        scan_and_track()
        print("Menunggu 15 menit untuk scan berikutnya...\n")
        time.sleep(900)
