import time, requests, io, pytz, json, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
import pandas as pd

# ===== CONFIGURATION NTFY =====
NTFY_XAU = os.getenv("NTFY_XAU", "https://ntfy.sh/rick-xau-sma-secret-2026")
NTFY_EUR = os.getenv("NTFY_EUR", "https://ntfy.sh/rick-eur-sma-secret-2026")
NTFY_GBP = os.getenv("NTFY_GBP", "https://ntfy.sh/rick-gbp-sma-secret-2026")
NTFY_V75 = os.getenv("NTFY_V75", "https://ntfy.sh/rick-v75-sma-secret-2026")

PAIRS = {
    "XAUUSD": {"symbol": "GC=F", "ntfy": NTFY_XAU, "dec": 2, "name": "XAUUSD (Or)"},
    "EURUSD": {"symbol": "EURUSD=X", "ntfy": NTFY_EUR, "dec": 5, "name": "EURUSD"},
    "GBPUSD": {"symbol": "GBPUSD=X", "ntfy": NTFY_GBP, "dec": 5, "name": "GBPUSD"},
    "V75": {"symbol": "R_75", "ntfy": NTFY_V75, "dec": 2, "name": "Volatility 75", "source": "deriv"},
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def send(url, title, msg, img=None):
    for i in range(5):
        try:
            h = {"Title": title}
            if img:
                h["Filename"] = "chart.png"
                h["X-Message"] = msg
                r = requests.post(url, data=img, headers={k: v.encode('utf-8') for k, v in h.items()}, timeout=30)
            else:
                r = requests.post(url, data=msg.encode('utf-8'), headers=h, timeout=15)
            if r.status_code == 200:
                log(f"✅ {title}")
                return True
            log(f"⚠️ Tentative {i+1}: status {r.status_code}")
            time.sleep(2**i)
        except Exception as e:
            log(f"❌ Erreur: {e}")
            time.sleep(2**i)
    return False

def get_candles_deriv(sym, granularity=60):
    try:
        import websocket as ws_client
        log(f"🔌 Connexion Deriv pour {sym}...")
        ws = ws_client.create_connection('wss://ws.binaryws.com/websockets/v3?app_id=1089', timeout=10)
        ws.send(json.dumps({"ticks_history": sym, "count": 100, "end": "latest", "start": 1, "style": "candles", "granularity": granularity}))
        r = json.loads(ws.recv())
        ws.close()
        if "candles" in r:
            candles = [{"t": c["epoch"], "o": float(c["open"]), "h": float(c["high"]), "l": float(c["low"]), "c": float(c["close"])} for c in r["candles"]]
            log(f"✅ Deriv: {len(candles)} bougies pour {sym}")
            return candles
        else:
            log(f"⚠️ Deriv: pas de bougies pour {sym}")
            return []
    except Exception as e:
        log(f"❌ Deriv {sym}: {e}")
        return []

def get_candles(sym, interval="1h", range_days="60d"):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&range={range_days}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()["chart"]["result"][0]
        closes = data["indicators"]["quote"][0]["close"]
        opens = data["indicators"]["quote"][0]["open"]
        highs = data["indicators"]["quote"][0]["high"]
        lows = data["indicators"]["quote"][0]["low"]
        timestamps = data["timestamp"]
        candles = []
        for i in range(len(closes)):
            if closes[i] and opens[i] and highs[i] and lows[i]:
                candles.append({"t": timestamps[i], "o": opens[i], "h": highs[i], "l": lows[i], "c": closes[i]})
        candles = candles[-100:] if len(candles) > 100 else candles
        log(f"✅ Yahoo: {len(candles)} bougies pour {sym} en {interval}")
        return candles
    except Exception as e:
        log(f"❌ Yahoo {sym}: {e}")
        return []

def calc_atr(candles, period=14):
    if len(candles) < period + 1:
        return 0.0
    tr_list = []
    for i in range(1, len(candles)):
        h = candles[i]["h"]
        l = candles[i]["l"]
        c_prev = candles[i-1]["c"]
        tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
        tr_list.append(tr)
    atr = sum(tr_list[-period:]) / period
    return atr

def chart_sma(cd, cp, sma3, sma10, info, title_suffix="", sl_price=None):
    if len(cd) < 5:
        return None
    name, dec = info["name"], info["dec"]
    fig, ax = plt.subplots(figsize=(18,10))
    fig.patch.set_facecolor('#0a0a0a')
    ax.set_facecolor('#0d1117')
    for i, c in enumerate(cd):
        col = '#26a69a' if c["c"]>=c["o"] else '#ef5350'
        ax.plot([i,i], [c["l"],c["h"]], color=col, lw=1.2)
        ax.add_patch(plt.Rectangle((i-0.35, min(c["o"],c["c"])), 0.7, abs(c["c"]-c["o"]) or 0.0001, facecolor=col, edgecolor=col))
    
    ax.plot(range(len(cd)), sma3, color='#3fb950', lw=2, label='SMA 3')
    ax.plot(range(len(cd)), sma10, color='#f85149', lw=2, label='SMA 10')
    
    ax.axhline(cp, color='#f59e0b', ls='-.', lw=3)
    ax.text(2, cp, f' Entrée: {cp:.{dec}f}', color='#f59e0b', fontsize=14, va='bottom', fontweight='bold', bbox=dict(boxstyle='round,pad=0.4', facecolor='#1a1400', alpha=0.85))

    if sl_price:
        ax.axhline(sl_price, color='#ef5350', ls='--', lw=2.5)
        ax.text(2, sl_price, f' Stop-Loss: {sl_price:.{dec}f}', color='#ef5350', fontsize=14, va='top', fontweight='bold', bbox=dict(boxstyle='round,pad=0.4', facecolor='#1a0a0a', alpha=0.85))

    n = len(cd)
    step = max(1, n//8)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([datetime.fromtimestamp(cd[i]["t"]).strftime('%d/%m\n%Hh') for i in range(0,n,step)], color='white', fontsize=11)
    ax.set_title(f"  {name} {title_suffix} — SMA 3/10 Croisement | Prix: {cp:.{dec}f}", color='white', fontsize=16, fontweight='bold', pad=15)
    ax.set_ylabel("Prix", color='white', fontsize=13)
    ax.tick_params(colors='white', labelsize=11)
    ax.grid(True, alpha=0.12, color='gray')
    for sp in ax.spines.values():
        sp.set_color('#333333')
    ax.legend(loc='upper left', facecolor='#1a1a2e', edgecolor='#555', labelcolor='white', fontsize=12, framealpha=0.9)
    plt.tight_layout(pad=1.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, facecolor='#0a0a0a')
    buf.seek(0)
    plt.close()
    return buf.getvalue()

def analyze_sma(key, info):
    log(f"🔍 Analyse SMA Multi-TF (H2 + H1 + M15) {key}...")
    src = info.get("source", "yahoo")

    if src == "deriv":
        candles_h2 = get_candles_deriv(info["symbol"], granularity=7200)
        candles_h1 = get_candles_deriv(info["symbol"], granularity=3600)
        candles_m15 = get_candles_deriv(info["symbol"], granularity=900)
    else:
        candles_h2 = get_candles(info["symbol"], interval="1h", range_days="60d")
        if len(candles_h2) >= 2:
            df = pd.DataFrame(candles_h2)
            df['t'] = pd.to_datetime(df['t'], unit='s')
            df.set_index('t', inplace=True)
            resampled = df.resample('2H').agg({'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last'}).dropna()
            candles_h2 = [{"t": int(ts.timestamp()), "o": row['o'], "h": row['h'], "l": row['l'], "c": row['c']} for ts, row in resampled.iterrows()]
            candles_h2 = candles_h2[-50:]
        candles_h1 = get_candles(info["symbol"], interval="1h", range_days="7d")
        candles_m15 = get_candles(info["symbol"], interval="15m", range_days="3d")

    if not candles_h2 or not candles_h1 or not candles_m15:
        log(f"⚠️ Pas de données pour {key}")
        return

    # Calcul des SMA
    closes_h2 = pd.Series([c["c"] for c in candles_h2])
    sma3_h2 = closes_h2.rolling(3).mean().values
    sma10_h2 = closes_h2.rolling(10).mean().values

    closes_h1 = pd.Series([c["c"] for c in candles_h1])
    sma3_h1 = closes_h1.rolling(3).mean().values
    sma10_h1 = closes_h1.rolling(10).mean().values

    closes_m15 = pd.Series([c["c"] for c in candles_m15])
    sma3_m15 = closes_m15.rolling(3).mean().values
    sma10_m15 = closes_m15.rolling(10).mean().values

    cp = candles_m15[-1]["c"]
    dec = info["dec"]
    atr_m15 = calc_atr(candles_m15, 14)
    seuil_atr_min = 0.00008 if key in ["EURUSD", "GBPUSD"] else (0.4 if key == "XAUUSD" else 4.0)

    # Tendances H2 et H1
    tendance_h2 = "LATERALE"
    if len(sma3_h2) >= 2 and len(sma10_h2) >= 2:
        if sma3_h2[-1] > sma10_h2[-1]: tendance_h2 = "HAUSSIERE"
        elif sma3_h2[-1] < sma10_h2[-1]: tendance_h2 = "BAISSIERE"

    tendance_h1 = "LATERALE"
    if len(sma3_h1) >= 2 and len(sma10_h1) >= 2:
        if sma3_h1[-1] > sma10_h1[-1]: tendance_h1 = "HAUSSIERE"
        elif sma3_h1[-1] < sma10_h1[-1]: tendance_h1 = "BAISSIERE"

    condition_remplie = False
    conseil = ""
    msg = ""
    sl_price = 0.0
    tolerance = 0.0004 if key in ["EURUSD", "GBPUSD"] else (1.0 if key == "XAUUSD" else 10.0)

    if len(sma3_m15) >= 2 and len(sma10_m15) >= 2:
        cross_up = sma3_m15[-2] <= sma10_m15[-2] and sma3_m15[-1] > sma10_m15[-1]
        cross_down = sma3_m15[-2] >= sma10_m15[-2] and sma3_m15[-1] < sma10_m15[-1]

        # Condition stricte : H2 et H1 doivent être d'accord avec le signal M15
        if cross_up and tendance_h2 == "HAUSSIERE" and tendance_h1 == "HAUSSIERE":
            condition_remplie = True
            recent_low = min([c["l"] for c in candles_m15[-5:]])
            sl_price = recent_low - tolerance
            conseil = "ACHAT (SMA H2+H1 Haussier + M15 Cross)"
            msg = f"SIGNAL ACHAT SMA PRO\nH2 & H1: HAUSSIERES | M15 Valide\nEntree approx: {cp:.{dec}f}\n🛑 Stop-Loss Tolérable: {sl_price:.{dec}f}"

        elif cross_down and tendance_h2 == "BAISSIERE" and tendance_h1 == "BAISSIERE":
            condition_remplie = True
            recent_high = max([c["h"] for c in candles_m15[-5:]])
            sl_price = recent_high + tolerance
            conseil = "VENTE (SMA H2+H1 Baissier + M15 Cross)"
            msg = f"SIGNAL VENTE SMA PRO\nH2 & H1: BAISSIERES | M15 Valide\nEntree approx: {cp:.{dec}f}\n🛑 Stop-Loss Tolérable: {sl_price:.{dec}f}"

    if condition_remplie:
        if atr_m15 < seuil_atr_min:
            log(f"⏭️ SILENCE {key} - Signal détecté mais ATR M15 trop faible ({atr_m15:.5f}) [Marché plat]")
            return

        full_msg = f"{msg}\n\nPrix M15: {cp:.{dec}f}\nTendance H2: {tendance_h2} | H1: {tendance_h1}\nATR M15: {atr_m15:.{dec}f}\n{datetime.now(pytz.timezone('Africa/Porto-Novo')).strftime('%H:%M')}H Benin\nSMA Bot Pro Multi-TF"

        log(f"📤 SIGNAL {key} - {conseil}")
        send(info["ntfy"], f"ALERTE {key} - {conseil}", full_msg)

        img_h1 = chart_sma(candles_h1, cp, sma3_h1, sma10_h1, info, "H1 Trend", sl_price)
        if img_h1:
            time.sleep(1)
            send(info["ntfy"], f"{key} H1 - Trend", "SMA H1", img_h1)

        img_m15 = chart_sma(candles_m15, cp, sma3_m15, sma10_m15, info, "M15 Trigger", sl_price)
        if img_m15:
            time.sleep(1)
            send(info["ntfy"], f"{key} M15 - Trigger & SL", "SMA M15", img_m15)
    else:
        log(f"⏭️ SILENCE {key} - Pas de consensus SMA (H2:{tendance_h2} | H1:{tendance_h1})")

if __name__ == "__main__":
    log("🚀 SMA BOT PRO - Croisement 3/10 (H2 + H1 + M15 + ATR + SL)")
    now = datetime.now(pytz.timezone('Africa/Porto-Novo'))
    h, j = now.hour, now.weekday()

    log("→ V75 (7j/7)")
    analyze_sma("V75", PAIRS["V75"])

    if j < 5:
        log(f"📊 Analyse Forex {h}H")
        for key in ["XAUUSD", "EURUSD", "GBPUSD"]:
            log(f"→ {key}")
            analyze_sma(key, PAIRS[key])
    else:
        log(f"💤 Forex ferme week-end")

    log("✅ Termine")
