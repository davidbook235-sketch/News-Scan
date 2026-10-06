"""News scanner: RSS headlines -> stock match -> sentiment score -> price confirmation."""
import re, math, time, calendar, requests, feedparser
from concurrent.futures import ThreadPoolExecutor

HOURS = 24
FEEDS = [
 "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
 "https://www.moneycontrol.com/rss/latestnews.xml",
 "https://www.moneycontrol.com/rss/marketreports.xml",
 "https://www.moneycontrol.com/rss/business.xml",
 "https://www.business-standard.com/rss/markets-106.rss",
 "https://news.google.com/rss/search?q=NSE+shares+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
 "https://news.google.com/rss/search?q=stocks+India+results+order+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
]
ALIAS = {"SBIN": ["SBI"], "LT": ["L&T"], "M&M": ["M&M"], "TATAMOTORS": ["Tata Motors"], "RELIANCE": ["Reliance", "RIL"],
         "ETERNAL": ["Zomato"], "BHARTIARTL": ["Airtel"], "MARUTI": ["Maruti"], "HINDUNILVR": ["HUL"], "INDIGO": ["IndiGo"],
         "BAJAJ-AUTO": ["Bajaj Auto"], "IRCTC": ["IRCTC"], "ADANIPORTS": ["Adani Ports"], "TCS": ["TCS"]}
POS = {"order win":3,"bags order":3,"wins order":3,"secures order":3,"bags":2,"profit jumps":3,"profit surges":3,"profit rises":2,
 "record profit":3,"beats estimates":3,"upgrade":2,"upgraded":2,"buy rating":2,"target raised":2,"raises target":2,
 "strong results":2,"margin expansion":2,"dividend":1,"buyback":2,"bonus":1,"approval":2,"usfda approval":3,
 "surges":2,"jumps":2,"rallies":1,"record high":2,"turnaround":2,"outperform":2,"stake buy":2}
NEG = {"fraud":-4,"sebi probe":-4,"sebi order":-3,"raid":-3,"default":-4,"downgrade":-2,"downgraded":-2,"sell rating":-2,
 "target cut":-2,"cuts target":-2,"profit falls":-3,"profit drops":-3,"net loss":-3,"loss widens":-3,"misses estimates":-3,
 "weak results":-2,"resigns":-2,"resignation":-2,"penalty":-2,"ban":-3,"usfda warning":-3,"usfda observations":-2,
 "plunges":-3,"slumps":-2,"tumbles":-2,"crash":-3,"insolvency":-4,"promoter pledge":-2,"order cancelled":-3,"probe":-2,"lawsuit":-2}
NEGATE = re.compile(r"\b(no|not|denies|denied|rejects|dismisses)\b", re.I)

def patterns(uni):
    out = []
    for sym, name in zip(uni.symbol, uni.name):
        base = re.sub(r"\s+(Ltd\.?|Limited)$", "", name, flags=re.I).strip()
        names = {base, *ALIAS.get(sym, [])}
        parts = [(f"(?-i:{re.escape(n)})" if len(n) <= 5 else re.escape(n)) for n in names if len(n) >= 3]
        if parts: out.append((sym, re.compile(r"(?<![\w&])(" + "|".join(parts) + r")(?![\w&])", re.I)))
    return out

def fetch(url):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        return feedparser.parse(r.content).entries
    except Exception:
        return []

def score_text(text):
    t = text.lower(); s = sum(w for k, w in {**POS, **NEG}.items() if k in t)
    return s * 0.3 if s > 0 and NEGATE.search(t) else s

def classify(score, p):
    if not p: return "NEWS ONLY"
    if score >= 2:
        if p["chg"] > -1 and p["above20"] and (p["volx"] >= 1.2 or p["chg"] > 0.5): return "BUY WATCH"
        return "TRAP? (price falling)" if p["chg"] < -1.5 else "WATCH"
    if score <= -2: return "AVOID/SELL" if (p["chg"] < 0 or not p["above20"]) else "NEG NEWS, price holding"
    return "NEUTRAL"

def run(uni, stats):
    with ThreadPoolExecutor(8) as ex: lists = list(ex.map(fetch, FEEDS))
    seen, items = set(), []
    for e in (x for l in lists for x in l):
        title = e.get("title", "").strip()
        if not title or title.lower() in seen: continue
        seen.add(title.lower())
        t = e.get("published_parsed") or e.get("updated_parsed")
        age = (time.time() - calendar.timegm(t)) / 3600 if t else 12
        if age <= HOURS: items.append((title, e.get("link", ""), age, score_text(title + " " + e.get("summary", "")[:200])))
    res = {}
    for title, link, age, s in items:
        if s == 0: continue
        for sym, rx in patterns_cache(uni):
            if rx.search(title):
                d = res.setdefault(sym, {"score": 0, "news": []})
                d["score"] += s * math.exp(-age / 12); d["news"].append({"t": title, "l": link, "s": round(s, 1)})
    rows = []
    for sym, d in res.items():
        if abs(d["score"]) < 1: continue
        p = stats.get(sym, {}); d["news"].sort(key=lambda n: -abs(n["s"]))
        rows.append({"symbol": sym, "score": round(d["score"], 1), "signal": classify(d["score"], p), **p, "news": d["news"][:3]})
    rows.sort(key=lambda r: -r["score"])
    return {"positive": [r for r in rows if r["score"] > 0][:15], "negative": [r for r in rows[::-1] if r["score"] < 0][:15]}

_cache = {}
def patterns_cache(uni):
    if "p" not in _cache: _cache["p"] = patterns(uni)
    return _cache["p"]
