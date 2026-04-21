import requests
import time
import sys

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL_HERE"
SYMBOL = "BTCUSDT"
WHALE_THRESHOLD = 500000
last_oi = 0
last_price = 0

# Virtual Tracker Variables
session_trades = []
current_position = None  # Stores {'type': 'LONG/SHORT', 'entry': price}

def get_market_data():
    global last_oi, last_price
    try:
        # 1. Price & Funding
        bitget_url = f"https://api.bitget.com/api/v2/mix/market/tickers?symbol={SYMBOL}&productType=USDT-FUTURES"
        ticker = requests.get(bitget_url, timeout=10).json()
        price = float(ticker['data'][0]['lastPr'])
        funding = float(ticker['data'][0]['fundingRate']) * 100

        # 2. Open Interest
        oi_url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={SYMBOL}"
        oi_resp = requests.get(oi_url, timeout=5).json()
        curr_oi = float(oi_resp.get('openInterest', 0)) * price if 'openInterest' in oi_resp else last_oi

        # Analysis Logic
        oi_trend = "Neutral"
        if last_oi > 0:
            if curr_oi < last_oi * 0.9995: oi_trend = "Weakening"
            elif curr_oi > last_oi * 1.0005: oi_trend = "Strengthening"

        price_trend = "Neutral"
        if last_price > 0:
            if price > last_price: price_trend = "Up"
            elif price < last_price: price_trend = "Down"

        # Probability Scoring
        long_score = 0
        short_score = 0
        if price_trend == "Up": long_score += 30
        if oi_trend == "Strengthening": long_score += 30
        if funding < 0: long_score += 40
        if price_trend == "Down": short_score += 30
        if oi_trend == "Weakening": short_score += 30
        if funding > 0.01: short_score += 40

        data = {"price": price, "funding": funding, "oi_trend": oi_trend, "long_prob": long_score, "short_prob": short_score}
        last_oi, last_price = curr_oi, price
        return data
    except Exception as e:
        print(f"Data Error: {e}")
        return None

def run_bot():
    global current_position
    print("--- Faiz's AI Trader & Tracker Live ---")
    try:
        while True:
            market = get_market_data()
            if market:
                price = market['price']

                # 1. Report Status to Discord
                msg = (f"━━━━━━━━━━━━━━━━━━━━\n"
                       f"📊 **MARKET REPORT**\n"
                       f"💰 Price: `${price}`\n"
                       f"📈 Bullish: `{market['long_prob']}%` | 📉 Bearish: `{market['short_prob']}%` \n"
                       f"━━━━━━━━━━━━━━━━━━━━")
                requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})

                # 2. Virtual Trade Logic
                # Entry Long
                if market['long_prob'] >= 70 and current_position is None:
                    current_position = {'type': 'LONG', 'entry': price}
                    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **VIRTUAL LONG OPENED** at `${price}`"})

                # Entry Short
                elif market['short_prob'] >= 70 and current_position is None:
                    current_position = {'type': 'SHORT', 'entry': price}
                    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🔻 **VIRTUAL SHORT OPENED** at `${price}`"})

                # Exit Logic (Close if probability drops or reverses)
                elif current_position:
                    pnl = 0
                    if current_position['type'] == 'LONG':
                        pnl = ((price - current_position['entry']) / current_position['entry']) * 100
                        if market['long_prob'] < 40:
                            session_trades.append(pnl)
                            requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🏁 **LONG CLOSED**. PNL: `{pnl:.2f}%`"})
                            current_position = None
                    elif current_position['type'] == 'SHORT':
                        pnl = ((current_position['entry'] - price) / current_position['entry']) * 100
                        if market['short_prob'] < 40:
                            session_trades.append(pnl)
                            requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🏁 **SHORT CLOSED**. PNL: `{pnl:.2f}%`"})
                            current_position = None

            time.sleep(60)

    except KeyboardInterrupt:
        # --- FINAL SESSION REPORT ---
        total_pnl = sum(session_trades)
        wins = len([t for t in session_trades if t > 0])
        total_t = len(session_trades)
        win_rate = (wins/total_t*100) if total_t > 0 else 0

        report = (f"━━━━━━━━━━━━━━━━━━━━\n"
                  f"🏁 **SESSION SUMMARY BY FAIZ**\n"
                  f"━━━━━━━━━━━━━━━━━━━━\n"
                  f"✅ Total Trades: `{total_t}`\n"
                  f"💰 Net Profit/Loss: `{total_pnl:.2f}%` \n"
                  f"🎯 Win Rate: `{win_rate:.1f}%` \n"
                  f"━━━━━━━━━━━━━━━━━━━━")
        requests.post(DISCORD_WEBHOOK_URL, json={"content": report})
        print("\nBot stopped. Summary sent to Discord.")
        sys.exit()

if __name__ == "__main__":
    run_bot()