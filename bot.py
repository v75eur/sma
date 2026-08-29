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
                r = requests.post(url, data=img, headers={k: v.encode() for k, v in h.items()}, timeout=30)
            else:
                r = requests.post(url, data=msg.encode(), headers=h, timeout=15)
            if r.status_code == 200:
                log(f"✅ {title}")
                return True
            log(f"⚠️ Tentative {i+1}: status {r.status_code}")
            time.sleep(2**i)
        except Exception as e:
            log(f"❌ Erreur: {e}")
            time.sleep(2**i)
    return False

# ===== RÉCUPÉRATION DES DONNÉES =====
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

# ===== CALCUL DES MOYENNES MOBILES =====
def calc_sma(candles, period=3):
    closes = [c["c"] for c in candles]
    if len(closes) < period:
        return [None] * len(closes)
    sma = []
    for i in range(len(closes)):
        if i < period - 1:
            sma.append(None)
        else:
            sma.append(sum(closes[i-period+1:i+1]) / period)
    return sma

def detect_cross(sma3, sma10):
    if len(sma3) < 2 or len(sma10) < 2:
        return None, False
    if sma3[-1] is None or sma10[-1] is None or sma3[-2] is None or sma10[-2] is None:
        return None, False
    if sma3[-1] > sma10[-1] and sma3[-2] <= sma10[-2]:
        return "HAUT", True
    elif sma3[-1] < sma10[-1] and sma3[-2] >= sma10[-2]:
        return "BAS", True
    return None, False

# ===== GRAPHIQUE STYLE MT5 =====
def chart_sma(candles, sma3, sma10, title, price, dec=2):
    if len(candles) < 20:
        return None
    
    fig, ax = plt.subplots(figsize=(18, 10))
    fig.patch.set_facecolor('#0a0a0a')
    ax.set_facecolor('#0d1117')
    
    # Chandeliers japonais
    for i, c in enumerate(candles):
        col = '#26a69a' if c["c"] >= c["o"] else '#ef5350'
        ax.plot([i, i], [c["l"], c["h"]], color=col, lw=1.2)
        ax.add_patch(plt.Rectangle((i-0.35, min(c["o"], c["c"])), 0.7, abs(c["c"]-c["o"]) or 0.0001, facecolor=col, edgecolor=col))
    
    # SMA 3 (bleue)
    ax.plot(range(len(sma3)), sma3, color='#00b4d8', lw=2, label='SMA 3')
    # SMA 10 (rouge)
    ax.plot(range(len(sma10)), sma10, color='#ff6b6b', lw=2, label='SMA 10')
    
    # Prix actuel
    ax.axhline(price, color='#f59e0b', ls='-.', lw=2, alpha=0.7)
    ax.text(len(candles)-1, price, f'  {price:.{dec}f}', color='#f59e0b', fontsize=12, fontweight='bold')
    
    ax.set_title(f"{title} - SMA (3,10)", color='white', fontsize=14, fontweight='bold')
    ax.set_ylabel("Prix", color='white', fontsize=12)
    ax.tick_params(colors='white')
    ax.grid(True, alpha=0.15, color='gray')
    ax.legend(loc='upper left', facecolor='#1a1a2e', edgecolor='#555', labelcolor='white', framealpha=0.9)
    
    plt.tight_layout(pad=1.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, facecolor='#0a0a0a')
    buf.seek(0)
    plt.close()
    return buf.getvalue()

# ===== ANALYSE PRINCIPALE =====
def analyze_sma(key, info):
    log(f"🔍 Analyse SMA {key}...")
    
    src = info.get("source", "yahoo")
    if src == "deriv":
        candles_h2 = get_candles_deriv(info["symbol"], granularity=7200)  # 2 heures
        candles_m15 = get_candles_deriv(info["symbol"], granularity=900)  # 15 minutes
    else:
        candles_h2 = get_candles(info["symbol"], interval="1h", range_days="60d")
        if len(candles_h2) >= 2:
            df = pd.DataFrame(candles_h2)
            df['t'] = pd.to_datetime(df['t'], unit='s')
            df.set_index('t', inplace=True)
            resampled = df.resample('2H').agg({
                'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last'
            }).dropna()
            candles_h2 = [{"t": int(ts.timestamp()), "o": row['o'], "h": row['h'], "l": row['l'], "c": row['c']} for ts, row in resampled.iterrows()]
            candles_h2 = candles_h2[-50:]
        candles_m15 = get_candles(info["symbol"], interval="15m", range_days="7d")
    
    if not candles_h2 or not candles_m15:
        log(f"⚠️ Pas de données pour {key}")
        return
    
    # Calcul des SMA H2
    sma3_h2 = calc_sma(candles_h2, 3)
    sma10_h2 = calc_sma(candles_h2, 10)
    
    # Calcul des SMA M15
    sma3_m15 = calc_sma(candles_m15, 3)
    sma10_m15 = calc_sma(candles_m15, 10)
    
    # Détection des croisements
    direction_h2, cross_h2 = detect_cross(sma3_h2, sma10_h2)
    direction_m15, cross_m15 = detect_cross(sma3_m15, sma10_m15)
    
    # Tendance H2 actuelle
    if sma3_h2[-1] is not None and sma10_h2[-1] is not None:
        if sma3_h2[-1] > sma10_h2[-1]:
            tendance_h2 = "HAUSSIERE"
            tendance_icon = "📈"
        else:
            tendance_h2 = "BAISSIERE"
            tendance_icon = "📉"
    else:
        tendance_h2 = "NEUTRE"
        tendance_icon = "📊"
    
    dec = info["dec"]
    cp = candles_m15[-1]["c"]
    now = datetime.now(pytz.timezone('Africa/Porto-Novo'))
    h = now.hour
    minute = now.minute
    
    msg = ""
    conseil = ""
    signal_type = ""
    condition_remplie = False
    
    # Cas 1 : Changement de tendance H2
    if cross_h2:
        if direction_h2 == "HAUT":
            signal_type = "CHANGEMENT TENDANCE HAUSSIERE"
            msg = f"📊 Tendance H2 DEVIENT HAUSSIERE\n✅ SMA 3 croise au-dessus de SMA 10"
            conseil = "🔍 Tendance HAUSSIERE confirmée (H2)"
        elif direction_h2 == "BAS":
            signal_type = "CHANGEMENT TENDANCE BAISSIERE"
            msg = f"📊 Tendance H2 DEVIENT BAISSIERE\n✅ SMA 3 croise en dessous de SMA 10"
            conseil = "🔍 Tendance BAISSIERE confirmée (H2)"
        condition_remplie = True
    
    # Cas 2 : Signal d'achat M15 (tendance H2 HAUSSIERE + croisement HAUT M15)
    elif cross_m15 and direction_m15 == "HAUT" and tendance_h2 == "HAUSSIERE":
        signal_type = "SIGNAL ACHAT"
        msg = f"📈 SIGNAL ACHAT SMA\n✅ Tendance HAUSSIERE (H2) confirmée\n✅ SMA 3 croise au-dessus SMA 10 sur M15"
        conseil = "📈 ACHAT (H2 HAUSSIER + M15 HAUT)"
        condition_remplie = True
    
    # Cas 3 : Signal de vente M15 (tendance H2 BAISSIERE + croisement BAS M15)
    elif cross_m15 and direction_m15 == "BAS" and tendance_h2 == "BAISSIERE":
        signal_type = "SIGNAL VENTE"
        msg = f"📉 SIGNAL VENTE SMA\n✅ Tendance BAISSIERE (H2) confirmée\n✅ SMA 3 croise en dessous SMA 10 sur M15"
        conseil = "📉 VENTE (H2 BAISSIER + M15 BAS)"
        condition_remplie = True
    
    # Cas 4 : Rien ne se passe (mais on envoie quand même un rapport)
    else:
        signal_type = "RAPPORT HORAIRE"
        msg = f"📊 RAPPORT SMA\n📊 Tendance H2: {tendance_icon} {tendance_h2}"
        if sma3_m15[-1] is not None and sma10_m15[-1] is not None:
            if sma3_m15[-1] > sma10_m15[-1]:
                msg += f"\n📊 M15: SMA3 > SMA10 (hausse courte)"
            else:
                msg += f"\n📊 M15: SMA3 < SMA10 (baisse courte)"
        conseil = "🔍 Surveillance SMA"
    
    full_msg = f"{msg}\n\n💰 Prix: {cp:.{dec}f}\n🕒 {h}:{minute:02d}H Bénin\n🤖 SMA Bot"
    
    log(f"📤 ENVOI RAPPORT {key} - {signal_type}...")
    send(info["ntfy"], f"{key} - {signal_type}", full_msg)
    
    time.sleep(1)
    
    # Graphique H2
    log(f"📤 Graphique H2 pour {key}...")
    img_h2 = chart_sma(candles_h2, sma3_h2, sma10_h2, f"{info['name']} H2", cp, dec)
    if img_h2:
        send(info["ntfy"], f"{key} H2 - {signal_type}", "SMA H2 (3,10)", img_h2)
    
    time.sleep(1)
    
    # Graphique M15
    log(f"📤 Graphique M15 pour {key}...")
    img_m15 = chart_sma(candles_m15, sma3_m15, sma10_m15, f"{info['name']} M15", cp, dec)
    if img_m15:
        send(info["ntfy"], f"{key} M15 - {signal_type}", "SMA M15 (3,10)", img_m15)

if __name__ == "__main__":
    log("🚀 SMA BOT - Stratégie H2 + M15")
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
