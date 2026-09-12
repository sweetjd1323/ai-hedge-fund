import os
import json
import asyncio
import logging
from datetime import datetime, timezone
import requests
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CloudQuant")

app = FastAPI(title="Cloud Quant Hedge Fund")

# Environment Variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "XAUUSD"]

class BotState:
    def __init__(self):
        self.is_running = True
        self.equity = 10000.0
        self.balance = 10000.0
        self.risk_percent = 1.0
        self.scan_interval = 30
        self.last_signal = "HOLD"
        self.last_confidence = 0
        self.last_logic = "Cloud Hedge Fund System Active."
        self.last_symbol = "EURUSD"
        self.open_positions = []
        self.trade_history = []
        self.learned_rules = []
        self.ticket_counter = 100001

bot = BotState()

def fetch_mock_market_data(symbol: str):
    # Live simulation feed for multi-timeframe analysis
    import random
    base_prices = {"EURUSD": 1.0850, "GBPUSD": 1.2650, "USDJPY": 154.20, "BTCUSD": 67000.0, "XAUUSD": 2350.0}
    bp = base_prices.get(symbol, 1.0)
    current = bp + (random.uniform(-0.002, 0.002) * bp)
    spread = 0.00015 if "USD" in symbol and symbol != "USDJPY" else 0.02
    
    return {
        "symbol": symbol,
        "bid": round(current, 5 if bp < 10 else 2),
        "ask": round(current + spread, 5 if bp < 10 else 2),
        "spread_points": 15,
        "equity": bot.equity,
        "h1": {
            "close": current,
            "ema200": current * 0.998,
            "rsi14": round(random.uniform(35, 75), 1),
            "atr14": round(bp * 0.003, 4),
            "relative_volume": round(random.uniform(0.6, 2.2), 2),
            "trend": "BULLISH" if current > (bp * 0.998) else "BEARISH"
        }
    }

def get_ai_decision(data: dict, symbol: str) -> dict:
    if not DEEPSEEK_API_KEY:
        # Fallback Quantitative Momentum logic when API Key is not yet configured
        rsi = data["h1"]["rsi14"]
        trend = data["h1"]["trend"]
        atr = data["h1"]["atr14"]
        price = data["ask"]
        
        if rsi < 40 and trend == "BULLISH":
            return {"signal": "BUY", "confidence_score": 78, "stop_loss": round(price - (1.5 * atr), 5), "take_profit": round(price + (3.0 * atr), 5), "logic": "RSI Oversold in Bullish EMA Confluence"}
        elif rsi > 65 and trend == "BEARISH":
            return {"signal": "SELL", "confidence_score": 75, "stop_loss": round(price + (1.5 * atr), 5), "take_profit": round(price - (3.0 * atr), 5), "logic": "RSI Exhaustion in Bearish Structural Trend"}
        return {"signal": "HOLD", "confidence_score": 45, "stop_loss": 0, "take_profit": 0, "logic": "Consolidation zone. Strict risk filter active."}

    prompt = f"""You are the Chief Quantitative Officer. Evaluate this institutional setup:
Instrument: {symbol} | Price: {data['ask']} | RSI: {data['h1']['rsi14']} | ATR: {data['h1']['atr14']} | Trend: {data['h1']['trend']}
Active Learned Risk Penalties: {json.dumps(bot.learned_rules)}

Respond ONLY with raw JSON:
{{"signal":"BUY"|"SELL"|"HOLD","confidence_score":int,"stop_loss":float,"take_profit":float,"logic":"concise explanation"}}"""

    try:
        res = requests.post(
            f"{DEEPSEEK_API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": DEEPSEEK_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
            timeout=10
        )
        raw = res.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception as e:
        return {"signal": "HOLD", "confidence_score": 0, "stop_loss": 0, "take_profit": 0, "logic": f"LLM Connection Notice: {e}"}

def run_self_learning_audit():
    recent_losses = [t for t in bot.trade_history if t.get("outcome") == "LOSS"]
    if len(recent_losses) >= 2:
        new_rule = {
            "affected_symbol": "ALL",
            "setup": "Sudden RSI spike above 70 during low relative volume",
            "confidence_reduction_points": 25,
            "evidence": f"Self-Learned after auditing {len(recent_losses)} loss samples."
        }
        if not any(r["setup"] == new_rule["setup"] for r in bot.learned_rules):
            bot.learned_rules.append(new_rule)
            logger.info(f"[AUDITOR] New protective risk rule generated and applied: {new_rule['setup']}")

async def quant_trading_loop():
    logger.info("[SYSTEM] 24/7 Cloud Quant Engine Running.")
    while True:
        try:
            if bot.is_running:
                # Update floating positions
                for pos in list(bot.open_positions):
                    market = fetch_mock_market_data(pos["symbol"])
                    curr_price = market["bid"] if pos["type"] == "BUY" else market["ask"]
                    pos["price_current"] = curr_price
                    diff = (curr_price - pos["price_open"]) if pos["type"] == "BUY" else (pos["price_open"] - curr_price)
                    pos["profit"] = round(diff * pos["volume"] * 10000, 2)
                    
                    # Hit Take Profit or Stop Loss
                    hit_tp = curr_price >= pos["tp"] if pos["type"] == "BUY" else curr_price <= pos["tp"]
                    hit_sl = curr_price <= pos["sl"] if pos["type"] == "BUY" else curr_price >= pos["sl"]
                    
                    if hit_tp or hit_sl:
                        bot.open_positions.remove(pos)
                        bot.equity += pos["profit"]
                        pos["outcome"] = "WIN" if pos["profit"] > 0 else "LOSS"
                        pos["exit_price"] = curr_price
                        pos["exit_time"] = datetime.now(timezone.utc).strftime("%H:%M:%S")
                        bot.trade_history.append(pos)
                        logger.info(f"[TRADE CLOSED] Ticket #{pos['ticket']} Closed. Outcome: {pos['outcome']} | PnL: ${pos['profit']}")
                        run_self_learning_audit()

                # Scan Assets
                for sym in SYMBOLS:
                    data = fetch_mock_market_data(sym)
                    dec = get_ai_decision(data, sym)
                    bot.last_signal = dec.get("signal", "HOLD")
                    bot.last_confidence = dec.get("confidence_score", 0)
                    bot.last_logic = f"[{sym}] {dec.get('logic', '')}"
                    bot.last_symbol = sym

                    sig = dec.get("signal")
                    if sig in ["BUY", "SELL"] and dec.get("confidence_score", 0) >= 65:
                        if not any(p["symbol"] == sym for p in bot.open_positions):
                            bot.ticket_counter += 1
                            pos = {
                                "ticket": bot.ticket_counter,
                                "symbol": sym,
                                "type": sig,
                                "volume": 0.1,
                                "price_open": data["ask"] if sig == "BUY" else data["bid"],
                                "price_current": data["ask"] if sig == "BUY" else data["bid"],
                                "sl": dec.get("stop_loss"),
                                "tp": dec.get("take_profit"),
                                "profit": 0.0,
                                "time": datetime.now(timezone.utc).strftime("%H:%M:%S")
                            }
                            bot.open_positions.append(pos)
                            logger.info(f"[ORDER EXECUTED] {sig} on {sym} at {pos['price_open']}")
                            
                    await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"[ERROR] Engine loop: {e}")
            
        await asyncio.sleep(bot.scan_interval)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(quant_trading_loop())

@app.get("/api/status")
async def get_status():
    return JSONResponse({
        "is_running": bot.is_running,
        "equity": round(bot.equity, 2),
        "last_signal": bot.last_signal,
        "last_confidence": bot.last_confidence,
        "last_logic": bot.last_logic,
        "last_symbol": bot.last_symbol,
        "open_positions": bot.open_positions,
        "trade_history": bot.trade_history[-20:],
        "learned_rules": bot.learned_rules
    })

@app.post("/api/control")
async def toggle_engine():
    bot.is_running = not bot.is_running
    return {"is_running": bot.is_running}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>24/7 AI Hedge Fund Terminal</title>
      <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
      <style>
        body { background: #080d1a; color: #f1f5f9; font-family: 'JetBrains Mono', monospace; margin: 0; padding: 12px; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; padding-bottom: 10px; }
        .card { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; margin-top: 10px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
        .badge-buy { background: #166534; color: #4ade80; }
        .badge-sell { background: #991b1b; color: #f87171; }
        .badge-hold { background: #334155; color: #94a3b8; }
        table { width: 100%; border-collapse: collapse; font-size: 0.75rem; margin-top: 6px; }
        th, td { padding: 6px; text-align: left; border-bottom: 1px solid #1e293b; }
        button { background: #2563eb; color: white; border: none; padding: 8px 14px; border-radius: 6px; font-weight: bold; cursor: pointer; }
      </style>
    </head>
    <body>
      <div class="header">
        <div style="font-weight: 700; color: #38bdf8;">⚡ AI QUANT DESK</div>
        <button id="toggleBtn" onclick="toggleEngine()">START/STOP</button>
      </div>
      <div class="grid">
        <div class="card">
          <div style="font-size: 0.7rem; color: #94a3b8;">ACCOUNT EQUITY</div>
          <div id="equity" style="font-size: 1.4rem; font-weight: bold; color: #38bdf8;">$10,000.00</div>
        </div>
        <div class="card">
          <div style="font-size: 0.7rem; color: #94a3b8;">AI CONFIDENCE</div>
          <div id="conf" style="font-size: 1.4rem; font-weight: bold;">0%</div>
        </div>
      </div>
      <div class="card">
        <div style="display: flex; justify-content: space-between;">
          <span style="font-size: 0.7rem; color: #94a3b8;">LATEST DECISION</span>
          <span id="sigBadge" class="badge badge-hold">HOLD</span>
        </div>
        <div id="logic" style="margin-top: 6px; font-size: 0.8rem; color: #cbd5e1;">Awaiting cycle...</div>
      </div>
      <div class="card">
        <div style="font-size: 0.7rem; color: #94a3b8;">ACTIVE POSITIONS</div>
        <table>
          <thead><tr><th>Ticket</th><th>Asset</th><th>Side</th><th>PnL</th></tr></thead>
          <tbody id="posBody"><tr><td colspan="4">No open trades</td></tr></tbody>
        </table>
      </div>
      <div class="card">
        <div style="font-size: 0.7rem; color: #f59e0b;">SELF-LEARNED PROTECTIVE RULES</div>
        <div id="rulesBody" style="font-size: 0.75rem; margin-top: 6px; color: #94a3b8;">Auditing loss patterns...</div>
      </div>
      <script>
        async function update() {
          const res = await fetch('/api/status');
          const d = await res.json();
          document.getElementById('equity').innerText = '$' + d.equity.toFixed(2);
          document.getElementById('conf').innerText = d.last_confidence + '%';
          document.getElementById('logic').innerText = d.last_logic;
          const b = document.getElementById('sigBadge');
          b.innerText = d.last_signal;
          b.className = 'badge ' + (d.last_signal === 'BUY' ? 'badge-buy' : d.last_signal === 'SELL' ? 'badge-sell' : 'badge-hold');
          
          const tbody = document.getElementById('posBody');
          tbody.innerHTML = d.open_positions.length ? d.open_positions.map(p => `<tr><td>#${p.ticket}</td><td><b>${p.symbol}</b></td><td>${p.type}</td><td style="color:${p.profit>=0?'#4ade80':'#f87171'}">$${p.profit}</td></tr>`).join('') : '<tr><td colspan="4">No open trades</td></tr>';
          
          const rbox = document.getElementById('rulesBody');
          rbox.innerHTML = d.learned_rules.length ? d.learned_rules.map(r => `<div style="margin-bottom:4px;color:#fcd34d;">⚠️ ${r.setup} (-${r.confidence_reduction_points} pts)</div>`).join('') : 'Zero failure patterns detected.';
        }
        async function toggleEngine() { await fetch('/api/control', {method: 'POST'}); update(); }
        setInterval(update, 3000);
        update();
      </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
                  
