import os
import sqlite3
import threading
import time
from datetime import datetime
from urllib.parse import quote_plus

import pytz
import requests

# ================= CONFIGURATION =================
TOKEN = "8591550376:AAF0VMvdW5K376uJS17L9eQ9gmW21RwXwuQ"
ADMIN_ID = 834018428
DB_NAME = "kodok_data.db"
INTERVAL = 180  # Broadcast tiap 3 menit
MIN_P2P_VOLUME_IDR = 50_000_000
MIN_P2P_VOLUME_SAR = 12_000
# =================================================


def setup_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS members (
        chat_id INTEGER PRIMARY KEY,
        joined_at TEXT
    )"""
    )
    conn.commit()
    conn.close()


def _to_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_md(text):
    return str(text).replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace("`", "")


def _build_p2p_link(fiat, trade_type, adv, advertiser):
    side = trade_type.lower()
    advertiser_no = adv.get("advertiserNo") or advertiser.get("advertiserNo") or advertiser.get("userNo")
    if advertiser_no:
        return (
            f"https://p2p.binance.com/en/trade/{side}/USDT"
            f"?fiat={fiat}&payment=ALL&publisher={advertiser_no}"
        )

    keyword = quote_plus(str(advertiser.get("nickName", "")))
    return f"https://p2p.binance.com/en/trade/{side}/USDT?fiat={fiat}&payment=ALL&keyword={keyword}"


def get_p2p_api(fiat, trade_type):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {"User-Agent": "Mozilla/5.0"}
    payload = {
        "asset": "USDT",
        "fiat": fiat,
        "merchantCheck": True,
        "page": 1,
        "rows": 30,
        "tradeType": trade_type,
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10).json()
        text = ""
        min_volume = MIN_P2P_VOLUME_IDR if fiat == "IDR" else MIN_P2P_VOLUME_SAR
        shown = 0

        for row in res.get("data", []):
            adv = row.get("adv", {})
            advertiser = row.get("advertiser", {})
            max_tx = _to_float(adv.get("dynamicMaxSingleTransAmount")) or _to_float(adv.get("maxSingleTransAmount"))

            if max_tx < min_volume:
                continue

            price = _to_float(adv.get("price"))
            name = _safe_md(advertiser.get("nickName", "Seller"))[:20]
            curr = "Rp" if fiat == "IDR" else "SAR"
            link = _build_p2p_link(fiat, trade_type, adv, advertiser)
            text += f"- [{name}]({link}) | {curr} {price:,.2f} | Limit {curr} {max_tx:,.0f}\n"

            shown += 1
            if shown >= 8:
                break

        return text if text else "- Belum ada seller dengan volume di atas batas."
    except Exception:
        return "- Connection Error"


def get_market_data():
    try:
        sar_res = requests.get("https://api.exchangerate-api.com/v4/latest/SAR", timeout=10).json()
        google_sar = sar_res["rates"]["IDR"]

        toko_res = requests.get("https://api.binance.me/api/v3/ticker/price?symbol=USDTIDR", timeout=10).json()
        tko_raw = float(toko_res["price"])

        tko_net = tko_raw * (1 + 0.2222 / 100)

        try:
            idx = float(requests.get("https://indodax.com/api/ticker/usdtidr", timeout=10).json()["ticker"]["last"])
        except Exception:
            idx = tko_raw

        tz = pytz.timezone("Asia/Jakarta")
        now_str = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")

        msg = "*KODOKLONCAT UPDATE*\n"
        msg += f"`{now_str} WIB`\n"
        msg += "----------------------\n"
        msg += "*CURRENCY RATES*\n"
        msg += f"- Google SAR  : Rp {google_sar:,.2f}\n"
        msg += f"- Tokocrypto  : Rp {tko_raw:,.2f}\n"
        msg += f"- + Biaya 0.2%: Rp {tko_net:,.2f}\n\n"

        msg += "*SIMULASI SAR (NET + FEE)*\n"
        for d in [3.78, 3.785, 3.79, 3.795, 3.8, 3.81, 3.82]:
            res_sim = tko_net / d
            msg += f"- Toko / {d}: Rp {res_sim:,.2f}\n"

        msg += "----------------------\n"
        msg += "*ESTIMASI CUAN (Rate 3.79)*\n"
        msg += "_Untung Google SAR - Simulasi_\n"
        untung_per_sar = google_sar - (tko_net / 3.79)
        for a in [20000, 50000, 100000, 200000, 300000]:
            cuan = untung_per_sar * a
            msg += f"- {int(a / 1000)}rb Riyal: +Rp {cuan:,.0f}\n"

        msg += "----------------------\n"
        msg += "*INDONESIA SPOT*\n"
        msg += f"- Tokocrypto : Rp {tko_raw:,.0f}\n"
        msg += f"- Indodax    : Rp {idx:,.0f}\n"
        msg += f"- Pintu Pro  : Rp {tko_raw:,.0f}\n"
        msg += f"- OSL        : Rp {tko_raw:,.0f}\n\n"

        msg += "*P2P Buy (Indo) - seller volume > 50jt:*\n"
        msg += get_p2p_api("IDR", "BUY") + "\n"
        msg += "*P2P Sell (Indo) - seller volume > 50jt:*\n"
        msg += get_p2p_api("IDR", "SELL") + "\n"
        msg += "----------------------\n"
        msg += "*SAUDI ARABIA P2P*\n"
        msg += "*P2P Buy (Saudi):*\n"
        msg += get_p2p_api("SAR", "BUY") + "\n"
        msg += "*P2P Sell (Saudi):*\n"
        msg += get_p2p_api("SAR", "SELL")

        return msg
    except Exception as e:
        return f"Error Fetching Data: {e}"


def listen_updates():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id + 1}&timeout=30"
            res = requests.get(url, timeout=35).json()
            if res.get("ok") and res.get("result"):
                for upd in res["result"]:
                    last_id = upd["update_id"]
                    if "message" not in upd:
                        continue
                    cid = upd["message"]["chat"]["id"]
                    txt = upd["message"].get("text", "")

                    if txt == "/start":
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute(
                            "INSERT OR IGNORE INTO members VALUES (?, ?)",
                            (cid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        )
                        conn.commit()
                        conn.close()
                        requests.post(
                            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                            data={
                                "chat_id": cid,
                                "text": "*KODOKRIYAL AKTIF!*\nUpdate otomatis tiap 3 menit.",
                                "parse_mode": "Markdown",
                            },
                            timeout=20,
                        )
        except Exception:
            time.sleep(5)


def broadcast_loop():
    while True:
        msg = get_market_data()
        conn = sqlite3.connect(DB_NAME)
        users = [r[0] for r in conn.execute("SELECT chat_id FROM members").fetchall()]
        conn.close()

        for mid in set(users + [ADMIN_ID]):
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    data={"chat_id": mid, "text": msg, "parse_mode": "Markdown"},
                    timeout=20,
                )
            except Exception:
                pass

        time.sleep(INTERVAL)


if __name__ == "__main__":
    setup_db()
    threading.Thread(target=listen_updates, daemon=True).start()
    print("KODOKRIYAL BOT running...")
    broadcast_loop()
