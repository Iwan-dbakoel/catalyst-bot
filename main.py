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

IDX_STOX = ['BBCA.JK', 'AMMN.JK', 'ITMG.JK', 'TOWR.JK', 'BRPT.JK']
US_STOX = ['NVDA', 'TSLA', 'AAPL', 'AMZN', 'AMD', 'META', 'MSFT', 'PLTR', 'LCID', 'SOFI']

# === SETUP DATABASE ===
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

# === OTAK ROBOT: MULTI-SESSION SCANNER ===
def get_market_session():
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    ny_tz = pytz.timezone('US/Eastern')
    
    now_jkt = datetime.now(jakarta_tz)
    now_ny = datetime.now(ny_tz)
    
    # Bursa IDX (Reguler) 09:00 - 15:30 WIB
    if 9 <= now_jkt.hour <= 15:
        return 'IDX_REG', IDX_STOX, now_jkt
        
    ny_hour = now_ny.hour
    ny_minute = now_ny.minute
    
    # Bursa US Pre-Market 04:00 - 09:30 EST
    if (4 <= ny_hour < 9) or (ny_hour == 9 and ny_minute < 30):
        return 'US_PRE', US_STOX, now_ny
        
    # Bursa US Reguler 09:30 - 16:00 EST
    elif (ny_hour == 9 and ny_minute >= 30) or (10 <= ny_hour <= 15):
        return 'US_REG', US_STOX, now_ny
        
    else:
        return 'CLOSED', [], now_ny

def scan_and_track():
    session, watchlist, current_time = get_market_session()
    
    if session == 'CLOSED':
        return

    print(f"[{current_time.strftime('%H:%M:%S')}] [{session}] Memindai & Tracking...")
    
    # 1. TRACKING POSISI EXISTING
    active_trades = get_active_signals()
    for trade in active_trades:
        ticker = trade[0]
        entry_price = trade[1]
        
        # Cek market match
        is_idx = '.JK' in ticker
        if (session.startswith('IDX') and not is_idx) or (session.startswith('US') and is_idx):
            continue
            
        try:
            # Untuk tracking, selalu pakai data reguler agar harga akurat
            data = yf.download(ticker, period='1d', interval='5m', prepost=False, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            if len(data) > 0:
                current_price = data['Close'].iloc[-1]
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                
                if pnl_pct >= 5.0:
                    msg = f"✅ <b>WIN TRACKED! [{session}]</b>\nTicker: <b>{ticker}</b>\nEntry: {entry_price:.2f}\nCurrent: {current_price:.2f}\nProfit: +{pnl_pct:.2f}%"
                    send_telegram_message(msg)
                    remove_signal(ticker)
                elif pnl_pct <= -3.0:
                    msg = f"❌ <b>LOSS TRACKED! [{session}]</b>\nTicker: <b>{ticker}</b>\nEntry: {entry_price:.2f}\nCurrent: {current_price:.2f}\nLoss: {pnl_pct:.2f}%"
                    send_telegram_message(msg)
                    remove_signal(ticker)
        except Exception as e:
            print(f"Error tracking {ticker}: {e}")

    # 2. CARI SAHAM BARU (CATALYST)
    for ticker in watchlist:
        if any(trade[0] == ticker for trade in active_trades):
            continue
            
        try:
            # Penting: prepost=True agar bisa baca data pre-market jika sesi US_PRE
            is_pre = (session == 'US_PRE')
            data = yf.download(ticker, period='1d', interval='5m', prepost=is_pre, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            if len(data) < 5:
                continue

            avg_vol = data['Volume'].iloc[:-1].mean()
            current_vol = data['Volume'].iloc[-1]
            current_price = data['Close'].iloc[-1]
            prev_close = data['Close'].iloc[-2]

            # Logika berbeda untuk Pre-Market vs Regular
            if session == 'US_PRE':
                # Pre-market volume tipis, jadi ambang batas volume lebih rendah (1.5x)
                # Tapi pergerakan harga harus besar (>3%)
                vol_mult = 1.5
                price_thresh = 3.0
                alert_title = "🟡 PRE-MARKET CATALYST"
            else:
                # Regular market butuh volume 3x dan harga naik 1%
                vol_mult = 3.0
                price_thresh = 1.0
                alert_title = "🚀 CATALYST DETECTED"

            if avg_vol > 0 and current_vol > (vol_mult * avg_vol):
                price_change_pct = ((current_price - prev_close) / prev_close) * 100
                if price_change_pct > price_thresh:
                    alert_msg = (
                        f"<b>{alert_title} [{session}]</b>\n"
                        f"Ticker: <b>{ticker}</b>\n"
                        f"Price: {current_price:.2f}\n"
                        f"Spike: +{price_change_pct:.2f}% (5m)\n"
                        f"Volume: {current_vol/1000:.0f}K ({vol_mult}x Normal)\n"
                        f"Action: Watch for ORB Breakout!"
                    )
                    send_telegram_message(alert_msg)
                    # Hanya simpan sinyal jika pasar reguler (bukan pre-market)
                    # Karena pre-market belum bisa dieksekusi oleh banyak broker
                    if session != 'US_PRE':
                        save_signal(ticker, current_price)
                    
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")

if __name__ == "__main__":
    init_db()
    send_telegram_message("✅ <b>Master Trader Bot V4 (Pre-Market Ready) Active.</b>\n🇮🇩 IDX & 🇺🇸 US (Pre/Reg) Auto-Tracking已激活。Memindai pasar...")
    while True:
        scan_and_track()
        print("Menunggu 10 menit untuk scan berikutnya...\n")
        time.sleep(600) # Turunkan ke 10 menit agar pre-market lebih sering dipantau
