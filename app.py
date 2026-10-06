import json, streamlit as st
st.set_page_config(page_title="Nifty 250 Scanner", page_icon="📈", layout="centered")
try: d = json.load(open("signals.json"))
except Exception:
    st.info("signals.json abhi nahi bana. GitHub > Actions > Scan > Run workflow chalao."); st.stop()
st.title("📈 Nifty 250 Scanner")
st.caption(f"Updated {d['updated']} | Scanned {d['scanned']} stocks | Free slots {d['slots']}/5")
cap = st.sidebar.number_input("Capital ₹", 10000, 10000000, int(d["capital"]), 10000)
rk = st.sidebar.slider("Risk per trade %", 0.5, 2.0, 1.0, 0.25)
(st.success if d["market_ok"] else st.warning)("Nifty > EMA50: market strong" if d["market_ok"] else "Nifty EMA50 ke neeche: sirf 5/5 setups dikhenge, size aadha rakho")
t1, t2, t3 = st.tabs(["Swing", "News", "Positions"])
with t1:
    if not d["swing"]: st.write("Abhi koi setup nahi.")
    for s in d["swing"]:
        q = max(0, min(int(cap * rk / 100 / s["risk"]), int(cap * 0.2 / s["entry"])))
        with st.expander(f"{s['symbol']} | {s['setup']} | {s['score']}/5 {s['news']}"):
            st.write(f"**Entry** {s['entry']} | **SL** {s['stop']} | **T1** {s['t1']} | **T2** {s['t2']}")
            st.write(f"**Qty {q}** (risk ₹{int(q*s['risk'])}) | RSI {s['rsi']} | Vol x{s['volx']} | RS vs Nifty {s['rs']}%")
            st.write(" ".join(("✅" if v else "❌") + k for k, v in s["checks"].items()))
with t2:
    for title, key in (("🟢 Positive news", "positive"), ("🔴 Negative news", "negative")):
        st.markdown(f"### {title}")
        for r in d["news"][key]:
            with st.expander(f"{r['symbol']} | {r['signal']} | {r['score']} | {r.get('chg','-')}%"):
                for n in r["news"]: st.markdown(f"- [{n['t']}]({n['l']})")
with t3:
    if not d["exits"]: st.write("positions.csv me trade daalo (GitHub par edit karke).")
    for e in d["exits"]:
        st.write(f"**{e['symbol']}** {e['status']} | Price {e['price']} | SL {e['stop']} | P&L {e['pnl_pct']}%")
st.caption("Sirf suggestion hai. Stop-loss ke bina trade na karein.")
