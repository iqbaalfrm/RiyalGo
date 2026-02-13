import time
import requests
import pytz
import os
from flask import Flask, render_template, jsonify
from datetime import datetime

app = Flask(__name__)


def _safe_get_json(url, timeout=10):
    try:
        return requests.get(url, timeout=timeout).json()
    except Exception:
        return {}


def _fetch_p2p(fiat, trade_type):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    payload = {
        "asset": "USDT",
        "fiat": fiat,
        "merchantCheck": True,
        "page": 1,
        "rows": 10,
        "tradeType": trade_type,
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10).json()
        data = res.get("data", [])
        return [{"name": x["advertiser"]["nickName"][:12], "price": float(x["adv"]["price"])} for x in data]
    except Exception:
        return []


def _fetch_xe_sar():
    """Fetch SAR/IDR rate from an alternative free API as XE.com backup."""
    try:
        res = requests.get("https://open.er-api.com/v6/latest/SAR", timeout=10).json()
        return float(res.get("rates", {}).get("IDR", 0.0))
    except Exception:
        return 0.0


def _fetch_indodax():
    """Fetch USDT/IDR price from INDODAX exchange."""
    try:
        res = requests.get("https://indodax.com/api/ticker/usdtidr", timeout=10).json()
        return float(res.get("ticker", {}).get("last", 0))
    except Exception:
        return 0.0


def _fetch_pintu():
    """Fetch USDT/IDR price from Pintu exchange."""
    try:
        res = requests.get("https://api.pintu.co.id/v2/trade/price-changes", timeout=10).json()
        for item in res.get("payload", []):
            if item.get("pair") == "usdt/idr":
                return float(item.get("latestPrice", 0))
        return 0.0
    except Exception:
        return 0.0


def get_market_engine():
    # 1. Kurs Real-time (Google / ExchangeRate API)
    sar_res = _safe_get_json("https://api.exchangerate-api.com/v4/latest/SAR")
    google_sar = float(sar_res.get("rates", {}).get("IDR", 0.0))

    # 1b. Kurs XE.com (alternative source)
    xe_sar = _fetch_xe_sar()

    # 2. TokoCrypto / Binance spot (with fallback)
    tko_res = _safe_get_json("https://api.binance.me/api/v3/ticker/price?symbol=USDTIDR")
    tko_raw = float(tko_res.get("price", 0.0))

    # Fallback: if Binance.me blocked, try Binance global USDT price via IDR conversion
    if not tko_raw:
        try:
            # Use Binance global BUSD/USDT or alternative
            binance_global = _safe_get_json("https://api.binance.com/api/v3/ticker/price?symbol=USDTBIDR")
            tko_raw = float(binance_global.get("price", 0.0))
        except Exception:
            pass

    # Fallback 2: use Indodax price if still 0
    if not tko_raw:
        tko_raw = _fetch_indodax()

    # 2b. INDODAX spot
    indodax_raw = _fetch_indodax()

    # 2c. PINTU spot
    pintu_raw = _fetch_pintu()

    # 2d. OSL — gunakan TokoCrypto sebagai estimasi (tidak ada public API gratis)
    osl_raw = tko_raw

    # 3. Pajak 0.2222%
    tko_net = tko_raw * (1 + 0.2222 / 100) if tko_raw else 0.0

    # 4. Simulasi Divider (Toko / X)
    divs = [3.78, 3.785, 3.79, 3.795, 3.8, 3.81, 3.82]
    sim_div = [{"label": f"Tokocrypto / {d}", "val": round(tko_net / d, 2) if tko_net else 0.0} for d in divs]

    # 5. Simulasi Profit Modal (Divider Acuan 3.79)
    base = (tko_net / 3.79) if tko_net else 0.0
    untung_per_sar = google_sar - base if google_sar and base else 0.0
    modals = [20000, 50000, 100000, 200000, 500000]
    profit_sim = []
    for a in modals:
        roi = (untung_per_sar / base * 100) if base else 0.0
        profit_sim.append({
            "sar": f"{a:,}",
            "idr": round(untung_per_sar * a),
            "roi": round(roi, 2)
        })

    # 6. Fetch P2P Data — BUY and SELL for both IDR and SAR
    p2p_indo_buy = _fetch_p2p("IDR", "BUY")
    p2p_indo_sell = _fetch_p2p("IDR", "SELL")
    p2p_saudi_buy = _fetch_p2p("SAR", "BUY")
    p2p_saudi_sell = _fetch_p2p("SAR", "SELL")

    tz = pytz.timezone("Asia/Jakarta")
    return {
        "time": datetime.now(tz).strftime("%H:%M:%S"),
        "date": datetime.now(tz).strftime("%d/%m/%Y"),
        "google_sar": google_sar,
        "xe_sar": xe_sar,
        "tko_raw": tko_raw,
        "tko_net": tko_net,
        "indodax_raw": indodax_raw,
        "pintu_raw": pintu_raw,
        "osl_raw": osl_raw,
        "sim_div": sim_div,
        "profit_sim": profit_sim,
        "p2p_indo_buy": p2p_indo_buy,
        "p2p_indo_sell": p2p_indo_sell,
        "p2p_saudi_buy": p2p_saudi_buy,
        "p2p_saudi_sell": p2p_saudi_sell,
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/data')
def api_data():
    return jsonify(get_market_engine())


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
