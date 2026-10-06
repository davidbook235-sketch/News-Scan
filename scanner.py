"""Main scanner: python scanner.py  -> signals.json (+ Telegram). Fast: ek hi batch download."""
import os, json, math, datetime as dt
import numpy as np, pandas as pd, requests, yfinance as yf
import universe, news

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
CAPITAL = float(os.getenv("CAPITAL", "100000"))
RISK_PCT, MAX_POS, MIN_TURNOVER, MAX_EXT = 0.01, 5, 1e8, 8.0   # 1% risk, 5 positions, 10Cr/day liquidity, 8% above EMA20

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))
def atr(df, n=14):
    pc = df.Close.shift()
    tr = pd.concat([df.High - df.Low, (df.High - pc).abs(), (df.Low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def get_frame(data, t, min_len=210):
    """Daily candles; market khula ho to aaj ki adhuri candle hata deta hai (completed-candle rule)."""
    try: df = data[t][["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception: return None
    if getattr(df.index, "tz", None) is not None: df.index = df.index.tz_localize(None)
    now = dt.datetime.now(IST)
    if len(df) and df.index[-1].date() == now.date() and now.time() < dt.time(15, 45): df = df.iloc[:-1]
    return df if len(df) >= min_len else None

def analyze(sym, df, nret):
    c, v = df.Close, df.Volume
    last = float(c.iloc[-1])
    e20, e50, e200 = (float(ema(c, n).iloc[-1]) for n in (20, 50, 200))
    a, r = float(atr(df).iloc[-1]), float(rsi(c).iloc[-1])
    volx = float(v.iloc[-1] / v.iloc[-21:-1].mean())
    stats = {"price": round(last, 2), "chg": round((last / float(c.iloc[-2]) - 1) * 100, 2), "volx": round(volx, 2), "above20": bool(last > e20)}
    if (c * v).tail(20).mean() < MIN_TURNOVER or last < 50 or not a > 0 or r != r: return stats, None
    ret63 = last / float(c.iloc[-64]) - 1
    ext = (last / e20 - 1) * 100
    trend, rs = last > e50 > e200, ret63 > nret
    vol, mom = volx >= 1.3, 45 <= r <= 72
    breakout = last > float(df.High.iloc[-21:-1].max()) and volx >= 1.5
    pullback = trend and abs(last / e20 - 1) <= 0.03 and 40 <= r <= 58 and last > float(df.Open.iloc[-1]) and last > float(c.iloc[-2])
    setup = breakout or pullback
    score = sum([trend, rs, vol, mom, setup])
    if not (trend and setup) or score < 4 or ext > MAX_EXT: return stats, None
    stop = max(last - 2 * a, float(df.Low.iloc[-5:].min()) - 0.2 * a)
    stop = min(stop, last - a)
    risk = last - stop
    res = float(df.High.iloc[-121:-1].max())
    if res > last and (res - last) < 1.5 * risk: return stats, None          # upar resistance bahut paas
    return stats, {"symbol": sym, "setup": "Breakout" if breakout else "Pullback", "score": score,
        "checks": {"Trend": trend, "RelStrength": rs, "Volume": vol, "Momentum": mom, "Setup": setup},
        "entry": round(last, 2), "stop": round(stop, 2), "risk": round(risk, 2),
        "t1": round(last + 1.5 * risk, 2), "t2": round(last + 3 * risk, 2), "rsi": round(r, 1), "volx": round(volx, 2),
        "rs": round((ret63 - nret) * 100, 1), "date": str(df.index[-1].date())}

def check_positions(data):
    """positions.csv ke trades: trailing stop update + EXIT alert."""
    if not os.path.exists("positions.csv"): return [], 0
    pos = pd.read_csv("positions.csv"); out = []
    for i, p in pos.iterrows():
        df = get_frame(data, str(p.symbol) + ".NS", 60)
        if df is None: continue
        last, a = float(df.Close.iloc[-1]), float(atr(df).iloc[-1])
        sub = df[df.index >= pd.Timestamp(p.date)]
        hi = float(sub.Close.max()) if len(sub) else last
        stop, status = float(p.stop), "HOLD"
        if hi >= p.entry + 2 * a:                                  # profit me ho to stop upar le jao
            new = max(stop, float(p.entry), hi - 2.5 * a)
            if new > stop + 0.01: stop, status = round(new, 2), "TRAIL STOP UP"
        if last <= stop: status = "EXIT"
        elif status == "HOLD" and last < float(ema(df.Close, 20).iloc[-1]): status = "WEAK (below EMA20)"
        pos.loc[i, "stop"] = stop
        out.append({"symbol": p.symbol, "entry": float(p.entry), "price": round(last, 2), "stop": stop, "qty": int(p.qty),
                    "pnl_pct": round((last / p.entry - 1) * 100, 2), "status": status, "date": str(df.index[-1].date())})
    pos.to_csv("positions.csv", index=False)
    return out, len(pos)

def telegram(items):
    tok, chat = os.getenv("TG_TOKEN"), os.getenv("TG_CHAT")
    if not (tok and chat) or not items: return
    sent = json.load(open("sent.json")) if os.path.exists("sent.json") else []
    new = [(k, t) for k, t in items if k not in sent]
    for i in range(0, len(new), 8):
        txt = "\n\n".join(t for _, t in new[i:i+8])
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": chat, "text": txt}, timeout=15)
    json.dump((sent + [k for k, _ in new])[-500:], open("sent.json", "w"))

def main():
    uni = universe.load(); syms = uni.symbol.tolist()
    data = yf.download([s + ".NS" for s in syms] + ["^NSEI"], period="1y", interval="1d", group_by="ticker",
                       threads=True, progress=False, auto_adjust=True)
    nd = get_frame(data, "^NSEI", 70); market_ok, nret = True, 0.0
    if nd is not None:
        market_ok = bool(nd.Close.iloc[-1] > ema(nd.Close, 50).iloc[-1]); nret = float(nd.Close.iloc[-1] / nd.Close.iloc[-64] - 1)
    stats, sigs = {}, []
    for s in syms:
        df = get_frame(data, s + ".NS")
        if df is None: continue
        st, sg = analyze(s, df, nret); stats[s] = st
        if sg: sigs.append(sg)
    nws = news.run(uni, stats)
    ns = {r["symbol"]: r["score"] for r in nws["positive"] + nws["negative"]}
    final = []
    for sg in sigs:
        sc = ns.get(sg["symbol"], 0)
        if sc <= -2 or (not market_ok and sg["score"] < 5): continue    # bad news ya weak market me kamzor setup skip
        sg["news"] = "news+" if sc >= 2 else ""; final.append(sg)
    final.sort(key=lambda x: (-x["score"], -x["rs"]))
    exits, npos = check_positions(data)
    out = {"updated": dt.datetime.now(IST).strftime("%d %b %Y %H:%M IST"), "market_ok": market_ok, "capital": CAPITAL,
           "slots": max(0, MAX_POS - npos), "scanned": len(stats), "swing": final[:15], "exits": exits, "news": nws}
    json.dump(out, open("signals.json", "w"), indent=1)
    msgs = []
    for s in final[:out["slots"] or 3]:
        q = max(0, min(int(CAPITAL * RISK_PCT / s["risk"]), int(CAPITAL * 0.2 / s["entry"])))
        msgs.append((f'{s["symbol"]}:{s["setup"]}:{s["date"]}', f'🟢 {s["symbol"]} {s["setup"]} {s["score"]}/5 {s["news"]}\nEntry {s["entry"]} | SL {s["stop"]} | T1 {s["t1"]} | T2 {s["t2"]} | Qty {q}'))
    for e in exits:
        if e["status"] in ("EXIT", "TRAIL STOP UP"):
            msgs.append((f'{e["symbol"]}:{e["status"]}:{e["date"]}', f'{"🔴" if e["status"]=="EXIT" else "🔼"} {e["symbol"]} {e["status"]}\nPrice {e["price"]} | SL {e["stop"]} | P&L {e["pnl_pct"]}%'))
    for r in nws["positive"][:5] + nws["negative"][:5]:
        if r["signal"] in ("BUY WATCH", "AVOID/SELL"):
            msgs.append((f'N:{r["symbol"]}:{r["signal"]}:{out["updated"][:11]}', f'📰 {r["symbol"]} {r["signal"]} (news {r["score"]})\n{r["news"][0]["t"]}'))
    telegram(msgs)

if __name__ == "__main__":
    main()
