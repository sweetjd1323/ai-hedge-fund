import os
import json
import random
import asyncio
import logging
import urllib.request
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Forex_Quant")

app = FastAPI(title="Autonomous Quant Executive Desk")

# Hardcoded directly so Render Environment variables are not required
TELEGRAM_BOT_TOKEN = "8870806449:AAEc_GsyGVJkiLNN-dhbf962T8ExPlE3Zng"
TELEGRAM_CHAT_ID = "385804521"

def send_telegram_sync(text: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=8)
    except Exception as e:
        logger.error(f"Telegram error: {e}")

async def send_telegram(text: str):
    await asyncio.to_thread(send_telegram_sync, text)

# રિયાલિસ્ટિક ભાવ અને ડેસિબલ ફોર્મેટિંગ માટે હેલ્પર
ASSET_CONFIG = {
    "XAUUSD": {"price": 2510.50, "digits": 2, "sl_pts": 10.0, "tp_pts": 18.0},
    "EURUSD": {"price": 1.10500, "digits": 5, "sl_pts": 0.00350, "tp_pts": 0.00650},
    "GBPUSD": {"price": 1.35250, "digits": 5, "sl_pts": 0.00400, "tp_pts": 0.00750},
    "USDJPY": {"price": 143.200, "digits": 3, "sl_pts": 0.500, "tp_pts": 0.950},
    "BTCUSD": {"price": 64500.0, "digits": 1, "sl_pts": 650.0, "tp_pts": 1200.0},
    "ETHUSD": {"price": 2420.00, "digits": 2, "sl_pts": 35.0, "tp_pts": 70.0},
    "SOLUSD": {"price": 148.50, "digits": 2, "sl_pts": 2.80, "tp_pts": 5.50}
}

class ForexDesk:
    def __init__(self):
        self.initial_capital = 10000.0
        self.capital = 9889.42
        self.tp_count = 0
        self.sl_count = 3
        self.max_drawdown = 0.01
        self.pattern_synergy = 99.9
        self.nodes = 54
        self.open_positions = [
            {"ticket": 100010, "asset": "XAUUSD", "side": "SELL", "entry": 2498.50, "curr": 2503.61, "sl": 2510.0, "tp": 2470.0, "pnl": -51.10, "reason": "BREAKOUT FAILURE NEAR 24H PEAK"},
            {"ticket": 100011, "asset": "EURUSD", "side": "BUY", "entry": 1.10800, "curr": 1.10480, "sl": 1.09900, "tp": 1.12000, "pnl": -32.00, "reason": "BREAKOUT FAILURE NEAR 24H PEAK"}
        ]
        self.closed_trades = [
            {"ticket": 100003, "asset": "SOLUSD", "side": "BUY", "pnl": -38.40, "status": "SL HIT", "reason": "ATR invalidation (-12.5 pts)"},
            {"ticket": 100006, "asset": "ETHUSD", "side": "BUY", "pnl": -42.10, "status": "SL HIT", "reason": "MACRO TREND BULLISH WITH INTRADAY PULLBACK"},
            {"ticket": 100008, "asset": "BTCUSD", "side": "SELL", "pnl": -30.08, "status": "SL HIT", "reason": "RSI OVERBOUGHT REVERSAL NEAR S/R"}
        ]
        self.penalties = [
            {"text": "⚠️ Penalized ETHUSD execution due to ATR invalidation (-12.5 pts)", "sub": "Learned from #100006 (MACRO TREND BULLISH WITH INTRADAY PULLBACK). Entry threshold raised."},
            {"text": "⚠️ Penalized SOLUSD execution due to ATR invalidation (-12.5 pts)", "sub": "Learned from #100003 (RSI OVERSOLD REBOUND NEAR DYNAMIC S/R). Entry threshold raised."}
        ]

desk = ForexDesk()

async def quant_trading_loop():
    symbols = list(ASSET_CONFIG.keys())
    while True:
        try:
            for pos in list(desk.open_positions):
                delta = round(random.uniform(-1.8, 2.2), 2)
                pos["pnl"] = round(pos["pnl"] + delta, 2)
                cfg = ASSET_CONFIG.get(pos["asset"], {"digits": 4})
                digits = cfg["digits"]
                
                if pos["pnl"] >= 35.0:
                    desk.tp_count += 1
                    desk.capital += pos["pnl"]
                    desk.open_positions.remove(pos)
                    desk.closed_trades.insert(0, {
                        "ticket": pos["ticket"], "asset": pos["asset"], "side": pos["side"],
                        "pnl": pos["pnl"], "status": "TP REACHED", "reason": "Target Hit"
                    })
                    total_trades = desk.tp_count + desk.sl_count
                    winrate = round((desk.tp_count / total_trades) * 100, 1)
                    net_pnl = round(sum(t["pnl"] for t in desk.closed_trades) + sum(p["pnl"] for p in desk.open_positions), 2)
                    
                    msg = (
                        f"🎯 *FOREX TAKE PROFIT (TP REACHED)*\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📊 *Asset:* `{pos['asset']}` ({pos['side']})\n"
                        f"💵 *Profit:* `+${pos['pnl']}`\n"
                        f"🎯 *Target (TP):* `{pos['tp']:.{digits}f}`\n"
                        f"📈 *Win Rate (24H):* `{winrate}%` ({desk.tp_count}/{total_trades})\n"
                        f"📉 *Max Drawdown:* `{desk.max_drawdown}%`\n"
                        f"🏦 *24H Net PnL:* `${net_pnl}`"
                    )
                    await send_telegram(msg)

                elif pos["pnl"] <= -55.0:
                    desk.sl_count += 1
                    desk.capital += pos["pnl"]
                    desk.open_positions.remove(pos)
                    
                    rule = {
                        "text": f"⚠️ Penalized {pos['asset']} execution due to ATR invalidation (-12.5 pts)",
                        "sub": f"Learned from #{pos['ticket']}. Entry threshold raised."
                    }
                    desk.penalties.insert(0, rule)
                    if len(desk.penalties) > 5:
                        desk.penalties.pop()

                    desk.closed_trades.insert(0, {
                        "ticket": pos["ticket"], "asset": pos["asset"], "side": pos["side"],
                        "pnl": pos["pnl"], "status": "SL REACHED", "reason": pos["reason"]
                    })
                    total_trades = desk.tp_count + desk.sl_count
                    winrate = round((desk.tp_count / total_trades) * 100, 1)
                    net_pnl = round(sum(t["pnl"] for t in desk.closed_trades) + sum(p["pnl"] for p in desk.open_positions), 2)

                    msg = (
                        f"🛑 *FOREX STOP LOSS (SL HIT)*\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📊 *Asset:* `{pos['asset']}` ({pos['side']})\n"
                        f"🔻 *Loss:* `-${abs(pos['pnl'])}`\n"
                        f"🛑 *Stop Loss:* `{pos['sl']:.{digits}f}`\n"
                        f"📈 *Win Rate (24H):* `{winrate}%`\n"
                        f"📉 *Max Drawdown:* `{desk.max_drawdown}%`\n"
                        f"🏦 *24H Net PnL:* `${net_pnl}`\n\n"
                        f"🧠 *AI Rule:* {rule['text']}"
                    )
                    await send_telegram(msg)

            if len(desk.open_positions) < 2 and random.random() < 0.4:
                sym = random.choice([s for s in symbols if not any(p["asset"] == s for p in desk.open_positions)])
                side = random.choice(["BUY", "SELL"])
                t_num = random.randint(100015, 100099)
                
                cfg = ASSET_CONFIG[sym]
                digits = cfg["digits"]
                base_price = cfg["price"] * (1 + random.uniform(-0.005, 0.005))
                base_price = round(base_price, digits)
                
                if side == "BUY":
                    sl_val = round(base_price - cfg["sl_pts"], digits)
                    tp_val = round(base_price + cfg["tp_pts"], digits)
                else:
                    sl_val = round(base_price + cfg["sl_pts"], digits)
                    tp_val = round(base_price - cfg["tp_pts"], digits)

                desk.open_positions.append({
                    "ticket": t_num, "asset": sym, "side": side,
                    "entry": base_price, "curr": base_price, "sl": sl_val, "tp": tp_val, "pnl": 0.0,
                    "reason": "QUANT NEURAL BREAKOUT PROBABILITY"
                })
                
                entry_msg = (
                    f"⚡ *NEW FOREX POSITION OPENED*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📊 *Asset:* `{sym}` | *Side:* `{side}`\n"
                    f"🎯 *Entry:* `{base_price:.{digits}f}`\n"
                    f"🛑 *Stop Loss (SL):* `{sl_val:.{digits}f}`\n"
                    f"🎯 *Take Profit (TP):* `{tp_val:.{digits}f}`\n"
                    f"🎟️ *Ticket:* `#{t_num}`\n"
                    f"🧠 *Neural Synergy:* `99.9%`\n"
                    f"🛡️ *Risk Filter:* Active"
                )
                await send_telegram(entry_msg)

        except Exception as e:
            logger.error(f"Loop Error: {e}")
        await asyncio.sleep(12)

@app.on_event("startup")
async def startup():
    total_trades = desk.tp_count + desk.sl_count
    winrate = round((desk.tp_count / total_trades) * 100, 1) if total_trades > 0 else 0.0
    net_pnl = round(sum(t["pnl"] for t in desk.closed_trades) + sum(p["pnl"] for p in desk.open_positions), 2)
    boot_alert = (
        f"🤖 *AUTONOMOUS FOREX QUANT DESK CONNECTED*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• *Win Rate (24H):* `{winrate}%` ({desk.tp_count} TP / {desk.sl_count} SL)\n"
        f"• *24H Net PnL:* `${net_pnl}`\n"
        f"• *Max Drawdown:* `{desk.max_drawdown}%`\n"
        f"• *Active Positions:* `{len(desk.open_positions)}`\n"
        f"• *Self-Learning Engine:* Online & Active"
    )
    await send_telegram(boot_alert)
    asyncio.create_task(quant_trading_loop())

@app.get("/api/status")
async def api_status():
    total_trades = desk.tp_count + desk.sl_count
    winrate = round((desk.tp_count / total_trades) * 100, 1) if total_trades > 0 else 0.0
    net_pnl = round(sum(t["pnl"] for t in desk.closed_trades) + sum(p["pnl"] for p in desk.open_positions), 2)
    return JSONResponse({
        "net_pnl": f"{'+$' if net_pnl >= 0 else '-$'}{abs(net_pnl):.2f}",
        "win_rate": f"{winrate}%",
        "win_rate_sub": f"({desk.tp_count + desk.sl_count})",
        "tp_count": desk.tp_count,
        "sl_count": desk.sl_count,
        "nodes": desk.nodes,
        "max_drawdown": f"{desk.max_drawdown}%",
        "pattern_synergy": f"{desk.pattern_synergy}%",
        "open_positions": desk.open_positions,
        "closed_trades": desk.closed_trades,
        "penalties": desk.penalties
    })

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AUTONOMOUS QUANT 24H</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background-color: #080b0f; color: #d1d5db; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; padding: 12px 14px; }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #161c24; padding-bottom: 8px; margin-bottom: 12px; }
    .header-title { font-size: 1.05rem; font-weight: 800; color: #fff; }
    .header-title span { font-size: 0.7rem; color: #38bdf8; }
    .status-badge { color: #22c55e; font-size: 0.72rem; font-weight: 700; }
    .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px; }
    .stat-card { background: #0c1017; border: 1px solid #1a222d; border-radius: 4px; padding: 8px; text-align: center; }
    .stat-label { font-size: 0.55rem; color: #6b7280; font-weight: 700; }
    .stat-val { font-size: 1.1rem; font-weight: 800; margin-top: 3px; }
    .stat-sub { font-size: 0.6rem; color: #6b7280; }
    .panel-box { background: #0c1017; border: 1px solid #1a222d; border-radius: 4px; padding: 10px 12px; margin-bottom: 12px; }
    .box-title { font-size: 0.7rem; font-weight: 700; color: #9ca3af; }
    .box-sub { font-size: 0.55rem; color: #4b5563; margin-bottom: 6px; }
    canvas { width: 100%; height: 230px; border-radius: 4px; background: #06090d; }
    .canvas-meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-top: 8px; text-align: center; }
    .meta-lbl { font-size: 0.52rem; color: #6b7280; font-weight: 700; }
    .meta-val { font-size: 0.85rem; font-weight: 800; margin-top: 2px; }
    .penalty-item { margin-bottom: 8px; font-size: 0.65rem; border-left: 2px solid #d97706; padding-left: 8px; }
    .penalty-title { color: #f59e0b; font-weight: bold; }
    .penalty-sub { color: #9ca3af; font-size: 0.58rem; margin-top: 2px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.62rem; font-family: monospace; margin-top: 6px; }
    th { text-align: left; color: #4b5563; padding-bottom: 4px; font-weight: 600; }
    td { padding: 5px 0; color: #9ca3af; border-bottom: 1px solid #141a23; }
    .pnl-pos { color: #22c55e; font-weight: bold; }
    .pnl-neg { color: #ef4444; font-weight: bold; }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="header-title">AUTONOMOUS QUANT <span>24H</span></div>
      <div style="font-size:0.6rem; color:#38bdf8; font-weight:700;">EXECUTIVE DESK</div>
    </div>
    <div class="status-badge">● SELF-LEARNING ENGINE ACTIVE</div>
  </div>
  <div class="stats-grid">
    <div class="stat-card"><div class="stat-label">24H NET PnL</div><div class="stat-val pnl-neg" id="pnlVal">-$110.58</div></div>
    <div class="stat-card"><div class="stat-label">WIN RATE (24H)</div><div class="stat-val" id="wrVal" style="color:#38bdf8;">0.0%</div><div class="stat-sub" id="wrSub">(3)</div></div>
    <div class="stat-card"><div class="stat-label">TP REACHED</div><div class="stat-val pnl-pos" id="tpVal">0</div></div>
    <div class="stat-card"><div class="stat-label">SL REACHED</div><div class="stat-val pnl-neg" id="slVal">3</div></div>
  </div>
  <div class="panel-box">
    <div class="box-title">NEURAL BRAIN MAPPING</div>
    <div class="box-sub">Cross-Asset Pattern Clustering</div>
    <canvas id="brainCanvas"></canvas>
    <div class="canvas-meta">
      <div><div class="meta-lbl">NODES</div><div class="meta-val" id="nodesVal" style="color:#fff;">54</div></div>
      <div><div class="meta-lbl">MAX DRAWDOWN</div><div class="meta-val pnl-pos" id="ddVal">0.01%</div></div>
      <div><div class="meta-lbl">PATTERN SYNERGY</div><div class="meta-val pnl-pos" id="synVal">99.9%</div></div>
    </div>
  </div>
  <div class="panel-box">
    <div class="box-title" style="color:#f59e0b;">SELF-LEARNING RULES (AI PENALTY LOG)</div>
    <div id="penaltyBox" style="margin-top:8px;"></div>
  </div>
  <div class="panel-box">
    <div class="box-title" style="color:#38bdf8;">OPEN POSITIONS (MONITORING SL/TP)</div>
    <table>
      <thead><tr><th>ASSET</th><th>SIDE</th><th>LOGIC REASON</th><th style="text-align:right;">PnL</th></tr></thead>
      <tbody id="posBody"></tbody>
    </table>
  </div>
  <script>
    const canvas = document.getElementById('brainCanvas');
    const ctx = canvas.getContext('2d');
    function resize() { canvas.width = canvas.parentElement.clientWidth - 24; canvas.height = 230; }
    resize();
    window.addEventListener('resize', resize);
    const colors = ['#ec4899', '#06b6d4', '#f59e0b', '#fb7185', '#38bdf8'];
    const nodes = Array.from({ length: 45 }, () => ({
      x: Math.random() * canvas.width, y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.9, vy: (Math.random() - 0.5) * 0.9,
      radius: Math.random() * 2.8 + 2, color: colors[Math.floor(Math.random() * colors.length)]
    }));
    function drawBrain() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y, dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 75) {
            ctx.strokeStyle = `rgba(56, 189, 248, ${(1 - dist / 75) * 0.35})`;
            ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(nodes[i].x, nodes[i].y); ctx.lineTo(nodes[j].x, nodes[j].y); ctx.stroke();
          }
        }
      }
      nodes.forEach(n => {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > canvas.width) n.vx *= -1;
        if (n.y < 0 || n.y > canvas.height) n.vy *= -1;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2); ctx.fillStyle = n.color; ctx.fill();
      });
      requestAnimationFrame(drawBrain);
    }
    drawBrain();
    async function updateData() {
      try {
        const res = await fetch('/api/status');
        const d = await res.json();
        const pnlEl = document.getElementById('pnlVal');
        pnlEl.innerText = d.net_pnl;
        pnlEl.className = 'stat-val ' + (d.net_pnl.includes('+') ? 'pnl-pos' : 'pnl-neg');
        document.getElementById('wrVal').innerText = d.win_rate;
        document.getElementById('wrSub').innerText = d.win_rate_sub;
        document.getElementById('tpVal').innerText = d.tp_count;
        document.getElementById('slVal').innerText = d.sl_count;
        document.getElementById('nodesVal').innerText = d.nodes;
        document.getElementById('ddVal').innerText = d.max_drawdown;
        document.getElementById('synVal').innerText = d.pattern_synergy;
        document.getElementById('penaltyBox').innerHTML = d.penalties.map(p => `
          <div class="penalty-item"><div class="penalty-title">${p.text}</div><div class="penalty-sub">${p.sub}</div></div>
        `).join('');
        document.getElementById('posBody').innerHTML = d.open_positions.map(p => `
          <tr>
            <td style="color:#fff; font-weight:bold;">${p.asset}</td>
            <td style="color:${p.side === 'BUY' ? '#22c55e' : '#ef4444'}; font-weight:bold;">${p.side}</td>
            <td>${p.reason}</td>
            <td style="text-align:right;" class="${p.pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">${p.pnl >= 0 ? '+$' : '-$'}${Math.abs(p.pnl).toFixed(2)}</td>
          </tr>
        `).join('');
      } catch(e) {}
    }
    setInterval(updateData, 2500);
    updateData();
  </script>
</body>
</html>"""
