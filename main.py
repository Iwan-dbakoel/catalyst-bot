import yfinance as yf
import pandas as pd
import requests
import time
import os
from datetime import datetime
import pytz

# === KONFIGURASI ===
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cyaehynqfynggtvhcvkg.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "MASUKKAN_SERVICE_ROLE_DISINI")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "MASUKKAN_TOKEN_DISINI")
CHAT_ID = os.getenv("CHAT_ID", "MASUKKAN_ID_DISINI")

# Header untuk mengakses Supabase via API (Tanpa library berat)
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

IDX_STOX = ['BBCA.JK', 'AMMN.JK', 'ITMG.JK', 'TOWR.JK', 'BRPT.JK']
US_STOX = ['NVDA', 'TSLA', 'AAPL', 'AMZN', 'AMD', 'META', 'MSFT', 'PLTR', 'LCID', 'SOFI']

# === FUNGSI DATABASE (VIA REST API) ===
def save_signal(ticker, price, market):
    url = f"{SUPABASE_URL}/rest/v1/active_signals"
    data = {"ticker": ticker, "entry_price": price, "market": market}
    requests.post(url, headers=SUPABASE_HEADERS, json=data)

def remove_signal(ticker):
    url = f"{SUPABASE_URL}/rest/v1/active_signals?ticker=eq.{ticker}"
    requests.delete(url, headers=SUPABASE_HEADERS)

def save_history(ticker, entry_price, exit_price, pnl_pct, status):
    url = f"{SUPABASE_URL}/rest/v1/trade_history"
    data = {"ticker": ticker, "entry_price": entry_price, "exit_price": exit_price, "pnl_pct": pnl_pct, "status": status}
    requests.post(url, headers=SUPABASE_HEADERS, json=data)

def get_active_signals(market):
    url = f"{SUPABASE_URL}/rest/v1/active_signals?market=eq.{market}"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    if resp.status_code == 200: return resp.json()
    return []

# === FUNGSI TELEGRAM ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try: requests.post(url, json=payload)
    except: pass

# === OTAK ROBOT ===
def get_market_session():
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    ny_tz = pytz.timezone('US/Eastern')
    now_jkt = datetime.now(jakarta_tz)
    now_ny = datetime.now(ny_tz)
    
    if 9 <= now_jkt.hour <= 15: return 'IDX', IDX_STOX, now_jkt
    ny_hour, ny_minute = now_ny.hour, now_ny.minute
    if (4 <= ny_hour < 9) or (ny_hour == 9 and ny_minute < 30): return 'US_PRE', US_STOX, now_ny
    elif (ny_hour == 9 and ny_minute >= 30) or (10 <= ny_hour <= 15): return 'US_REG', US_STOX, now_ny
    else: return 'CLOSED', [], now_jkt

def scan_and_track():
    session, watchlist, current_time = get_market_session()
    if session == 'CLOSED': return
    market_type = 'IDX' if 'IDX' in session else 'US'
    
    active_trades = get_active_signals(market_type)
    for trade in active_trades:
        ticker, entry_price = trade['ticker'], trade['entry_price']
        try:
            data = yf.download(ticker, period='1d', interval='5m', prepost=False, progress=False)
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            if len(data) > 0:
                current_price = data['Close'].iloc[-1]
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                if pnl_pct >= 5.0:
                    send_telegram_message(f"✅ <b>WIN TRACKED! [{session}]</b>\nTicker: <b>{ticker}</b>\nProfit: +{pnl_pct:.2f}%")
                    save_history(ticker, entry_price, current_price, pnl_pct, 'WIN')
                    remove_signal(ticker)
                elif pnl_pct <= -3.0:
                    send_telegram_message(f"❌ <b>LOSS TRACKED! [{session}]</b>\nTicker: <b>{ticker}</b>\nLoss: {pnl_pct:.2f}%")
                    save_history(ticker, entry_price, current_price, pnl_pct, 'LOSS')
                    remove_signal(ticker)
        except: pass

    active_tickers = [t['ticker'] for t in active_trades]
    for ticker in watchlist:
        if ticker in active_tickers: continue
        try:
            is_pre = (session == 'US_PRE')
            data = yf.download(ticker, period='1d', interval='5m', prepost=is_pre, progress=False)
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            if len(data) < 5: continue

            avg_vol = data['Volume'].iloc[:-1].mean()
            current_vol = data['Volume'].iloc[-1]
            current_price = data['Close'].iloc[-1]
            prev_close = data['Close'].iloc[-2]

            vol_mult, price_thresh = (1.5, 3.0) if is_pre else (3.0, 1.0)
            alert_title = "🟡 PRE-MARKET CATALYST" if is_pre else "🚀 CATALYST DETECTED"

            if avg_vol > 0 and current_vol > (vol_mult * avg_vol):
                price_change_pct = ((current_price - prev_close) / prev_close) * 100
                if price_change_pct > price_thresh:
                    send_telegram_message(f"<b>{alert_title} [{session}]</b>\nTicker: <b>{ticker}</b>\nPrice: {current_price:.2f}\nSpike: +{price_change_pct:.2f}%")
                    if session != 'US_PRE': save_signal(ticker, current_price, market_type)
        except: pass

if __name__ == "__main__":
    send_telegram_message("✅ <b>Master Trader Bot V6 (Optimized SaaS) Active.</b>\nRingan, Anti-Crash, & Terhubung Database!")
    while True:
        scan_and_track()
        time.sleep(600)
