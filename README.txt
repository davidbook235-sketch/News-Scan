MOBILE SETUP (sirf 5 steps)
1. GitHub par naya repo banao, is zip ki SAARI files upload karo (.github folder samet).
2. Repo > Settings > Secrets and variables > Actions: TG_TOKEN aur TG_CHAT daalo (Telegram ke liye).
   Optional: Variables me CAPITAL (default 100000).
3. Actions tab > "Scan" > Run workflow. 1-2 minute me signals.json ban jayega.
4. share.streamlit.io par repo select karo, Main file = app.py, Deploy.
5. Trade lene ke baad positions.csv edit karo:  symbol,entry,stop,qty,date
   Example: SBIN,820,795,10,2026-10-07   -> exit/trailing-stop alerts aane lagenge.
Login/API key ki zarurat nahi (data Yahoo Finance se, ek hi call me 250 stocks).
