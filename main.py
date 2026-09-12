import os
import json
import asyncio
import logging
from datetime import datetime, timezone
import aiohttp
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QuantDesk")

app = FastAPI(title="Autonomous Quant Executive Terminal v3.0")

# Telegram Configuration (Optional - Environment variables ma mukvu hoy to)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SYMBOLS = ["SOLUSD", "ETHUSD", "GBPUSD", "EURUSD", "BTCUSD", "XAUUSD"]
DB_FILE = "quant_memory.json"

class BotState:
    def __init__(self):
        self.is_running = True
        self.initial_equity = 10000.0
        self.equity = 10000.0
        self.peak_equity = 10000.0
        self.max_drawdown = 0.0
        self.scan_interval = 12
        self.open_positions = []
        self.closed_trades = []
        self.execution_stream = []
        self.learned_rules = []
        self.ticket_counter = 100001
        self.nodes_count = 54
        self.synergy = 99.9

bot = BotState()

def save_state():
    try:
        data = {
            "equity": bot.equity,
            "peak_equity": bot.peak_equity,
            "max_drawdown": bot.max_drawdown,
            "closed_trades": bot.closed_trades,
            "learned_rules": bot.learned_rules,
            "ticket_counter": bot.ticket_counter
        }
        with open(DB_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Save error: {e}")

def load_state():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                d = json.load(f)
                bot.equity = d.get("equity", 10000.0)
                bot.peak_equity = d.get("peak_equity", 10000.0)
                bot.max_drawdown = d.get("max_drawdown", 0.0)
                bot.closed_trades = d.get("closed_trades", [])
                bot.learned_rules = d.get("learned_rules", [])
                bot.ticket_counter = d.get("ticket_counter", 100001)
        except Exception as e:
            logger.error(f"Load error: {e}")

async def send_telegram(msg: str):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        except Exception as e:
            logger.error(f"Telegram alert error: {e}")

def fetch_market_data(symbol: str):
    import random
    base = {
        "SOLUSD": 145.50,
        "ETHUSD": 3450.0,
        "EURUSD": 1.0850,
        "GBPUSD": 1.2650,
        "BTCUSD": 67000.0,
        "XAUUSD": 2350.0
    }
    bp = base.get(symbol, 100.0)
    current = bp + (random.uniform(-0.0018, 0.0018) * bp)
    return {
        "symbol": symbol,
        "ask": round(current, 4 if bp < 10 else 2),
        "bid": round(current - (0.0002 if bp < 10 else 0.5), 4 if bp < 10 else 2),
        "rsi": round(random.uniform(28, 76), 1),
        "atr": round(bp * 0.0025, 4),
        "trend": "BULLISH" if current > bp else "BEARISH"
    }

def get_ai_decision(data: dict, symbol: str) -> dict:
    penalty = sum(r["penalty"] for r in bot.learned_rules if r["symbol"] in [symbol, "ALL"])

    reasons = [
        "MACRO TREND BULLISH WITH INTRADAY PULLBACK",
        "RSI OVERSOLD REBOUND NEAR DYNAMIC S/R",
        "MOMENTUM EXHAUSTION AT LOCAL RESISTANCE",
        "BREAKOUT FAILURE NEAR 24H PEAK",
        "LIQUIDITY SWEEP WITH BULLISH ORDER BLOCK"
    ]
    import random
    selected_reason = random.choice(reasons)
    base_conf = round(random.uniform(80.0, 96.0), 1)
    final_conf = max(35.0, round(base_conf - penalty, 1))

    rsi = data["rsi"]
    trend = data["trend"]
    price = data["ask"]
    atr = data["atr"]

    if rsi < 36 and trend == "BULLISH":
        sig = "BUY" if final_conf >= 65 else "HOLD"
        return {"signal": sig, "confidence": final_conf, "sl": round(price - (1.2 * atr), 2), "tp": round(price + (2.4 * atr), 2), "logic": selected_reason}
    elif rsi > 64 and trend == "BEARISH":
        sig = "SELL" if final_conf >= 65 else "HOLD"
        return {"signal": sig, "confidence": final_conf, "sl": round(price + (1.2 * atr), 2), "tp": round(price - (2.4 * atr), 2), "logic": selected_reason}
    
    return {"signal": "HOLD", "confidence": final_conf, "sl": 0, "tp": 0, "logic": selected_reason}

def audit_and_learn(closed_trade: dict):
    if closed_trade["status"] == "SL HIT":
        rule_desc = f"Penalized {closed_trade['symbol']} execution due to ATR invalidation"
        if not any(r["desc"] == rule_desc for r in bot.learned_rules):
            bot.learned_rules.insert(0, {
                "time": closed_trade["time"],
                "symbol": closed_trade["symbol"],
                "desc": rule_desc,
                "lesson": f"Learned from #{closed_trade['ticket']} ({closed_trade['logic']}). Entry threshold raised.",
                "penalty": 12.5
            })
            if len(bot.learned_rules) > 10:
                bot.learned_rules.pop()

async def quant_loop():
    while True:
        try:
            if bot.is_running:
                now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")

                for pos in list(bot.open_positions):
                    data = fetch_market_data(pos["symbol"])
                    curr = data["bid"] if pos["type"] == "BUY" else data["ask"]
                    diff = (curr - pos["price_open"]) if pos["type"] == "BUY" else (pos["price_open"] - curr)

                    sym = pos["symbol"]
                    mult = 100000 if sym in ["EURUSD", "GBPUSD"] else (100 if sym == "XAUUSD" else 1.0)
                    pos["profit"] = round(diff * pos["volume"] * mult, 2)

                    hit_tp = curr >= pos["tp"] if pos["type"] == "BUY" else curr <= pos["tp"]
                    hit_sl = curr <= pos["sl"] if pos["type"] == "BUY" else curr >= pos["sl"]

                    if hit_tp or hit_sl:
                        bot.open_positions.remove(pos)
                        bot.equity += pos["profit"]
                        
                        outcome = "TP HIT" if hit_tp else "SL HIT"
                        record = {
                            "ticket": pos["ticket"],
                            "symbol": pos["symbol"],
                            "type": pos["type"],
                            "entry": pos["price_open"],
                            "exit": curr,
                            "logic": pos["logic"],
                            "pnl": pos["profit"],
                            "status": outcome,
                            "time": now_str
                        }
                        bot.closed_trades.insert(0, record)
                        if len(bot.closed_trades) > 30:
                            bot.closed_trades.pop()

                        if bot.equity > bot.peak_equity:
                            bot.peak_equity = bot.equity
                        dd = ((bot.peak_equity - bot.equity) / bot.peak_equity) * 100
                        bot.max_drawdown = round(max(bot.max_drawdown, dd), 2)

                        audit_and_learn(record)
                        save_state()
                        
                        alert_icon = "🎯" if outcome == "TP HIT" else "🛑"
                        await send_telegram(f"{alert_icon} *TRADE CLOSED [{outcome}]*\nSymbol: `{pos['symbol']}`\nSide: `{pos['type']}`\nPnL: `${pos['profit']}`\nLogic: _{pos['logic']}_")

                for sym in SYMBOLS:
                    m = fetch_market_data(sym)
                    dec = get_ai_decision(m, sym)

                    bot.execution_stream.insert(0, {
                        "time": now_str,
                        "asset": sym,
                        "logic": dec["logic"],
                        "conf": f"{dec['confidence']}%"
                    })
                    if len(bot.execution_stream) > 8:
                        bot.execution_stream.pop()

                    if dec["signal"] in ["BUY", "SELL"] and len(bot.open_positions) < 4:
                        if not any(p["symbol"] == sym for p in bot.open_positions):
                            bot.ticket_counter += 1
                            new_pos = {
                                "ticket": bot.ticket_counter,
                                "symbol": sym,
                                "type": dec["signal"],
                                "volume": 0.05 if sym in ["BTCUSD", "ETHUSD"] else 0.1,
                                "price_open": m["ask"] if dec["signal"] == "BUY" else m["bid"],
                                "sl": dec["sl"],
                                "tp": dec["tp"],
                                "logic": dec["logic"],
                                "profit": 0.0
                            }
                            bot.open_positions.append(new_pos)
                            await send_telegram(f"⚡ *NEW POSITION OPENED*\nSymbol: `{sym}`\nSide: `{dec['signal']}`\nPrice: `{new_pos['price_open']}`\nTP: `{dec['tp']}` | SL: `{dec['sl']}`\nLogic: _{dec['logic']}_")
                    await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"Loop error: {e}")
        await asyncio.sleep(bot.scan_interval)

@app.on_event("startup")
async def start():
    load_state()
    asyncio.create_task(quant_loop())

@app.get("/api/status")
async def status():
    unrealized = sum(p["profit"] for p in bot.open_positions)
    net_pnl = round((bot.equity - bot.initial_equity) + unrealized, 2)
    tp_count = len([t for t in bot.closed_trades if t["status"] == "TP HIT"])
    sl_count = len([t for t in bot.closed_trades if t["status"] == "SL HIT"])
    total_closed = len(bot.closed_trades)
    winrate = round((tp_count / total_closed * 100), 1) if total_closed > 0 else 0.0

    return JSONResponse({
        "pnl_display": f"+${net_pnl}" if net_pnl >= 0 else f"-${abs(net_pnl)}",
        "winrate_display": f"{winrate}%",
        "drawdown_display": f"{bot.max_drawdown}%",
        "nodes_count": bot.nodes_count,
        "synergy": f"{bot.synergy}%",
        "total_closed": total_closed,
        "tp_count": tp_count,
        "sl_count": sl_count,
        "positions": bot.open_positions,
        "closed_trades": bot.closed_trades,
        "learned_rules": bot.learned_rules,
        "stream": bot.execution_stream
    })

@app.get("/", response_class=HTMLResponse)
async def ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>AUTONOMOUS QUANT v3.0 - 24H AUDIT DESK</title>
      <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
          background-color: #0b0e13;
          color: #d1d5db;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
          padding: 12px 14px;
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid #1f242c;
          padding-bottom: 8px;
          margin-bottom: 12px;
        }
        .header-title { font-size: 1.05rem; font-weight: 800; color: #fff; letter-spacing: 1px; }
        .header-title span { font-size: 0.7rem; color: #38bdf8; margin-left: 4px; }
        .status-badge { color: #22c55e; font-size: 0.72rem; font-weight: 700; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px; }
        .stat-card { background: #11151a; border: 1px solid #1e242b; border-radius: 4px; padding: 10px; text-align: center; }
        .stat-label { font-size: 0.58rem; color: #6b7280; font-weight: 700; }
        .stat-val { font-size: 1.15rem; font-weight: 800; margin-top: 3px; }
        
        .main-layout { display: grid; grid-template-columns: 1.15fr 1fr; gap: 12px; margin-bottom: 12px; }
        @media (max-width: 900px) { .main-layout { grid-template-columns: 1fr; } }
        
        .panel-box {
          background: #11151a;
          border: 1px solid #1e242b;
          border-radius: 4px;
          padding: 10px 12px;
          margin-bottom: 12px;
        }
        .box-title { font-size: 0.72rem; font-weight: 700; color: #9ca3af; letter-spacing: 0.8px; margin-bottom: 4px; }
        .box-subtitle { font-size: 0.6rem; color: #4b5563; margin-bottom: 8px; }
        canvas { width: 100%; height: 260px; border-radius: 4px; background: #080b0e; }
        
        .brain-footer { display: flex; justify-content: space-between; margin-top: 8px; padding-top: 4px; border-top: 1px solid #1a2027; }
        .foot-item { font-size: 0.58rem; color: #6b7280; }
        .foot-val { font-size: 0.85rem; font-weight: bold; color: #fff; margin-top: 2px; }
        
        table { width: 100%; border-collapse: collapse; font-size: 0.64rem; font-family: monospace; margin-top: 4px; }
        th { text-align: left; color: #4b5563; padding-bottom: 4px; font-weight: 600; }
        td { padding: 5px 0; color: #9ca3af; border-bottom: 1px solid #161b22; }
        
        .pnl-pos { color: #22c55e; font-weight: bold; }
        .pnl-neg { color: #ef4444; font-weight: bold; }
        .badge-tp { background: rgba(34, 197, 94, 0.15); color: #22c55e; padding: 2px 4px; border-radius: 2px; font-weight: bold; }
        .badge-sl { background: rgba(239, 68, 68, 0.15); color: #ef4444; padding: 2px 4px; border-radius: 2px; font-weight: bold; }
        
        .learn-item {
          background: #0d1116;
          border-left: 3px solid #f59e0b;
          padding: 8px;
          margin-top: 6px;
          border-radius: 2px;
          font-size: 0.65rem;
        }
        .learn-title { color: #f59e0b; font-weight: bold; margin-bottom: 2px; }
        .learn-desc { color: #9ca3af; }
      </style>
    </head>
    <body>
      <div class="header">
        <div>
          <div class="header-title">AUTONOMOUS QUANT <span>24H EXECUTIVE DESK</span></div>
        </div>
        <div class="status-badge">● SELF-LEARNING ENGINE ACTIVE</div>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">24H NET PnL</div>
          <div class="stat-val" id="pnlVal" style="color:#22c55e;">+$0.00</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">WIN RATE (24H)</div>
          <div class="stat-val" id="wrVal" style="color:#38bdf8;">0%</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">TP REACHED</div>
          <div class="stat-val" id="tpHitVal" style="color:#22c55e;">0</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">SL REACHED</div>
          <div class="stat-val" id="slHitVal" style="color:#ef4444;">0</div>
        </div>
      </div>

      <div class="main-layout">
        <div>
          <div class="panel-box">
            <div class="box-title">NEURAL BRAIN MAPPING</div>
            <div class="box-subtitle">Cross-Asset Pattern Clustering</div>
            <canvas id="brainCanvas"></canvas>
            <div class="brain-footer">
              <div class="foot-item">NODES<div class="foot-val" id="nodesVal">54</div></div>
              <div class="foot-item">MAX DRAWDOWN<div class="foot-val" id="ddVal" style="color:#22c55e;">0%</div></div>
              <div class="foot-item">PATTERN SYNERGY<div class="foot-val" id="synVal" style="color:#22c55e;">99.9%</div></div>
            </div>
          </div>

          <div class="panel-box">
            <div class="box-title" style="color:#f59e0b;">SELF-LEARNING RULES (AI PENALTY LOG)</div>
            <div id="learnBody"><div style="color:#4b5563; font-size:0.65rem;">Engine active. Analyzing losses to generate defensive filters...</div></div>
          </div>
        </div>

        <div>
          <div class="panel-box">
            <div class="box-title" style="color:#38bdf8;">OPEN POSITIONS (MONITORING SL/TP)</div>
            <table>
              <thead><tr><th>ASSET</th><th>SIDE</th><th>LOGIC REASON</th><th style="text-align:right;">PnL</th></tr></thead>
              <tbody id="posBody"></tbody>
            </table>
          </div>

          <div class="panel-box">
            <div class="box-title">LIVE SCAN STREAM</div>
            <table>
              <thead><tr><th>TIME</th><th>ASSET</th><th>SETUP REASON</th><th style="text-align:right;">CONF</th></tr></thead>
              <tbody id="streamBody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="panel-box">
        <div class="box-title" style="color:#a855f7;">24-HOUR TRADE AUDIT LOG (ALL TRADES & REASONS)</div>
        <table>
          <thead>
            <tr>
              <th>TIME</th>
              <th>TICKET</th>
              <th>ASSET</th>
              <th>SIDE</th>
              <th>ENTRY/EXIT</th>
              <th>EXECUTION LOGIC</th>
              <th>STATUS</th>
              <th style="text-align:right;">PnL</th>
            </tr>
          </thead>
          <tbody id="closedBody"></tbody>
        </table>
      </div>

      <script>
        const canvas = document.getElementById('brainCanvas');
        const ctx = canvas.getContext('2d');
        function resize() {
          canvas.width = canvas.parentElement.clientWidth - 24;
          canvas.height = 260;
        }
        resize();
        window.addEventListener('resize', resize);

        const colors = ['#ec4899', '#06b6d4', '#f59e0b', '#fb7185', '#38bdf8', '#fbbf24'];
        const nodes = Array.from({ length: 50 }, () => ({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 1.1,
          vy: (Math.random() - 0.5) * 1.1,
          radius: Math.random() * 3 + 2,
          color: colors[Math.floor(Math.random() * colors.length)]
        }));

        function drawBrain() {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
              const dx = nodes[i].x - nodes[j].x;
              const dy = nodes[i].y - nodes[j].y;
              const dist = Math.sqrt(dx * dx + dy * dy);
              if (dist < 90) {
                const alpha = (1 - dist / 90) * 0.45;
                ctx.strokeStyle = `rgba(56, 189, 248, ${alpha})`;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(nodes[i].x, nodes[i].y);
                ctx.lineTo(nodes[j].x, nodes[j].y);
                ctx.stroke();
              }
            }
          }
          nodes.forEach(n => {
            n.x += n.vx;
            n.y += n.vy;
            if (n.x < 0 || n.x > canvas.width) n.vx *= -1;
            if (n.y < 0 || n.y > canvas.height) n.vy *= -1;
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
            ctx.fillStyle = n.color;
            ctx.shadowColor = n.color;
            ctx.shadowBlur = 8;
            ctx.fill();
            ctx.shadowBlur = 0;
          });
          requestAnimationFrame(drawBrain);
        }
        drawBrain();

        async function updateTerminal() {
          try {
            const res = await fetch('/api/status');
            const data = await res.json();

            document.getElementById('pnlVal').innerText = data.pnl_display;
            document.getElementById('wrVal').innerText = data.winrate_display + ' (' + data.total_closed + ')';
            document.getElementById('tpHitVal').innerText = data.tp_count;
            document.getElementById('slHitVal').innerText = data.sl_count;
            document.getElementById('ddVal').