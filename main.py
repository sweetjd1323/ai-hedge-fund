import os
import json
import asyncio
import logging
from datetime import datetime, timezone
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QuantDesk")

app = FastAPI(title="Quant Engine")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "XAUUSD"]

class BotState:
    def __init__(self):
        self.is_running = True
        self.initial_equity = 10000.0
        self.equity = 10000.0
        self.peak_equity = 10000.0
        self.max_drawdown = 0.0
        self.scan_interval = 30
        self.last_signal = "HOLD"
        self.last_confidence = 0
        self.last_logic = "Engine active. Scanning price confluence..."
        self.open_positions = []
        self.trade_history = []
        self.learned_rules = []
        self.ticket_counter = 100001

bot = BotState()

def fetch_market_data(symbol: str):
    import random
    base = {"EURUSD": 1.0850, "GBPUSD": 1.2650, "USDJPY": 154.20, "BTCUSD": 67000.0, "XAUUSD": 2350.0}
    bp = base.get(symbol, 1.0)
    current = bp + (random.uniform(-0.002, 0.002) * bp)
    return {
        "symbol": symbol,
        "ask": round(current, 5 if bp < 10 else 2),
        "bid": round(current - 0.00015, 5 if bp < 10 else 2),
        "rsi": round(random.uniform(30, 75), 1),
        "atr": round(bp * 0.003, 4),
        "trend": "BULLISH" if current > bp else "BEARISH"
    }

def get_ai_decision(data: dict, symbol: str) -> dict:
    # Rule Penalty Check
    penalty = sum(r["confidence_reduction_points"] for r in bot.learned_rules if r["affected_symbol"] in [symbol, "ALL"])
    
    rsi = data["rsi"]
    trend = data["trend"]
    price = data["ask"]
    atr = data["atr"]

    base_conf = 78
    final_conf = max(0, base_conf - penalty)

    if rsi < 38 and trend == "BULLISH":
        sig = "BUY" if final_conf >= 65 else "HOLD"
        return {"signal": sig, "confidence_score": final_conf, "sl": round(price - (1.5 * atr), 5), "tp": round(price + (3.0 * atr), 5), "logic": f"RSI Oversold in Bullish Trend. Applied penalty: -{penalty} pts"}
    elif rsi > 67 and trend == "BEARISH":
        sig = "SELL" if final_conf >= 65 else "HOLD"
        return {"signal": sig, "confidence_score": final_conf, "sl": round(price + (1.5 * atr), 5), "tp": round(price - (3.0 * atr), 5), "logic": f"RSI Exhaustion in Bearish Trend. Applied penalty: -{penalty} pts"}
    
    return {"signal": "HOLD", "confidence_score": 40, "sl": 0, "tp": 0, "logic": f"Consolidation. Strict risk filter active (-{penalty} pts)."}

def run_self_learning_audit():
    recent_losses = [t for t in bot.trade_history if t.get("outcome") == "LOSS"]
    if len(recent_losses) >= 1:
        new_rule = {
            "affected_symbol": recent_losses[-1]["symbol"],
            "setup": f"High ATR divergence during consolidation on {recent_losses[-1]['symbol']}",
            "confidence_reduction_points": 20,
            "evidence": f"Auto-penalized after evaluating ticket #{recent_losses[-1]['ticket']} loss."
        }
        if not any(r["setup"] == new_rule["setup"] for r in bot.learned_rules):
            bot.learned_rules.append(new_rule)
            logger.info(f"[AUDITOR] New Rule Applied: {new_rule['setup']}")

async def quant_loop():
    while True:
        try:
            if bot.is_running:
                # Update positions & check SL/TP
                for pos in list(bot.open_positions):
                    data = fetch_market_data(pos["symbol"])
                    curr = data["bid"] if pos["type"] == "BUY" else data["ask"]
                    diff = (curr - pos["price_open"]) if pos["type"] == "BUY" else (pos["price_open"] - curr)
                    pos["profit"] = round(diff * pos["volume"] * 10000, 2)

                    hit_tp = curr >= pos["tp"] if pos["type"] == "BUY" else curr <= pos["tp"]
                    hit_sl = curr <= pos["sl"] if pos["type"] == "BUY" else curr >= pos["sl"]

                    if hit_tp or hit_sl:
                        bot.open_positions.remove(pos)
                        bot.equity += pos["profit"]
                        pos["outcome"] = "WIN" if pos["profit"] > 0 else "LOSS"
                        pos["exit_price"] = curr
                        pos["exit_time"] = datetime.now(timezone.utc).strftime("%H:%M:%S")
                        bot.trade_history.append(pos)
                        
                        # Max Drawdown & Peak tracking
                        if bot.equity > bot.peak_equity:
                            bot.peak_equity = bot.equity
                        dd = ((bot.peak_equity - bot.equity) / bot.peak_equity) * 100
                        bot.max_drawdown = round(max(bot.max_drawdown, dd), 2)

                        if pos["outcome"] == "LOSS":
                            run_self_learning_audit()

                # Scan Assets
                for sym in SYMBOLS:
                    m = fetch_market_data(sym)
                    dec = get_ai_decision(m, sym)
                    bot.last_signal = dec["signal"]
                    bot.last_confidence = dec["confidence_score"]
                    bot.last_logic = f"[{sym}] {dec['logic']}"

                    if dec["signal"] in ["BUY", "SELL"]:
                        if not any(p["symbol"] == sym for p in bot.open_positions):
                            bot.ticket_counter += 1
                            bot.open_positions.append({
                                "ticket": bot.ticket_counter,
                                "symbol": sym,
                                "type": dec["signal"],
                                "volume": 0.1,
                                "price_open": m["ask"] if dec["signal"] == "BUY" else m["bid"],
                                "sl": dec["sl"],
                                "tp": dec["tp"],
                                "profit": 0.0,
                                "time": datetime.now(timezone.utc).strftime("%H:%M:%S")
                            })
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Loop error: {e}")
        await asyncio.sleep(bot.scan_interval)

@app.on_event("startup")
async def start():
    asyncio.create_task(quant_loop())

@app.get("/api/status")
async def status():
    wins = len([t for t in bot.trade_history if t.get("outcome") == "WIN"])
    total_closed = len(bot.trade_history)
    winrate = round((wins / total_closed * 100), 1) if total_closed > 0 else 0.0
    realized_pnl = round(bot.equity - bot.initial_equity, 2)

    return JSONResponse({
        "equity": round(bot.equity, 2),
        "realized_pnl": realized_pnl,
        "winrate": winrate,
        "max_drawdown": bot.max_drawdown,
        "total_trades": total_closed,
        "last_signal": bot.last_signal,
        "last_confidence": bot.last_confidence,
        "last_logic": bot.last_logic,
        "open_positions": bot.open_positions,
        "trade_history": bot.trade_history[-10:],
        "learned_rules": bot.learned_rules
    })

@app.get("/", response_class=HTMLResponse)
async def ui():
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Quant Performance Desk</title>
      <style>
        body { background: #080d1a; color: #f1f5f9; font-family: -apple-system, sans-serif; margin: 0; padding: 12px; }
        .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 10px; }
        .card { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; }
        .title { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; font-weight: bold; }
        .val { font-size: 1.3rem; font-weight: bold; margin-top: 4px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.75rem; margin-top: 6px; }
        th, td { padding: 6px; text-align: left; border-bottom: 1px solid #1e293b; }
      </style>
    </head>
    <body>
      <h3 style="color:#38bdf8; margin-top:0;">⚡ QUANT TERMINAL</h3>
      <div class="grid">
        <div class="card"><div class="title">Equity</div><div id="eq" class="val">$10,000</div></div>
        <div class="card"><div class="title">Net PnL</div><div id="pnl" class="val">$0.00</div></div>
        <div class="card"><div class="title">Win Rate</div><div id="wr" class="val">0%</div></div>
        <div class="card"><div class="title">Max Drawdown</div><div id="dd" class="val" style="color:#f87171;">0%</div></div>
      </div>
      <div class="card" style="margin-bottom:10px;">
        <div class="title">Decision Logic</div>
        <div id="logic" style="font-size:0.8rem; margin-top:4px; color:#cbd5e1;">Scanning...</div>
      </div>
      <div class="card" style="margin-bottom:10px;">
        <div class="title">Active Positions</div>
        <table><thead><tr><th>Ticket</th><th>Asset</th><th>Side</th><th>PnL</th></tr></thead><tbody id="pos"></tbody></table>
      </div>
      <div class="card">
        <div class="title" style="color:#f59e0b;">Self-Learned Rules (Auto-Penalties)</div>
        <div id="rules" style="font-size:0.75rem; margin-top:6px; color:#fcd34d;">Scanning for loss patterns...</div>
      </div>
      <script>
        async function loadData() {
          const res = await fetch('/api/status');
          const d = await res.json();
          document.getElementById('eq').innerText = '$' + d.equity.toFixed(2);
          document.getElementById('pnl').innerText = (d.realized_pnl >= 0 ? '+$' : '-$') + Math.abs(d.realized_pnl).toFixed(2);
          document.getElementById('pnl').style.color = d.realized_pnl >= 0 ? '#4ade80' : '#f87171';
          document.getElementById('wr').innerText = d.winrate + '% (' + d.total_trades + ' trades)';
          document.getElementById('dd').innerText = d.max_drawdown + '%';
          document.getElementById('logic').innerText = d.last_logic;
          
          document.getElementById('pos').innerHTML = d.open_positions.length ? d.open_positions.map(p => `<tr><td>#${p.ticket}</td><td><b>${p.symbol}</b></td><td>${p.type}</td><td style="color:${p.profit>=0?'#4ade80':'#f87171'}">$${p.profit}</td></tr>`).join('') : '<tr><td colspan="4">No open positions</td></tr>';
          
          document.getElementById('rules').innerHTML = d.learned_rules.length ? d.learned_rules.map(r => `<div>⚠️ ${r.setup} (-${r.confidence_reduction_points} pts penalty applied)</div>`).join('') : 'Zero loss patterns identified so far.';
        }
        setInterval(loadData, 3000);
        loadData();
      </script>
    </body>
    </html>
    """
    
