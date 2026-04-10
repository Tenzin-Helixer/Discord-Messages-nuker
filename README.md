# ⌫ Wiper — Discord Message Deleter
A local desktop app to bulk-delete your own Discord messages from servers or channels. Built with Python + Tkinter, zero dependencies beyond the standard library.

⚠️ Using self-bots / automating your Discord account may violate Discord's ToS. Use at your own risk.
⌫ Wiper — Discord Message Deleter
A local desktop app to bulk-delete your own Discord messages from servers or channels. Built with Python + Tkinter, zero dependencies beyond the standard library.

⚠️ Using self-bots / automating your Discord account may violate Discord's ToS. Use at your own risk.
 
---

## 📸 Features

Guild search mode — finds and deletes all your messages across an entire server
Channel mode — sweeps a specific channel and deletes only your messages
Rate-limit aware — respects Discord's rate limits with automatic retry + jitter delays
Token security — your auth token is never saved to disk, never logged, and never sent anywhere except directly to Discord's API
100% local — no telemetry, no server, no internet traffic except to discord.com

---

## 🚀 Requirements

Python 3.8+
No external packages needed (uses only tkinter, urllib, threading, json from stdlib)


▶️ How to Run
bashpython wiper.py

On some Linux distros you may need to install tkinter separately:
bashsudo apt install python3-tk

---

## 🛠️ How to Use
Method A — Guild Search (Recommended)
Deletes your messages across an entire server.

Open Discord in Chrome (or any Chromium browser)
Go to any channel in the target server
Press F12 → go to the Network tab
Use Discord's search bar (top-right) → filter by From: You
In the Network tab, find the request matching:

   guilds/.../messages/search?author_id=...

Right-click it → Copy → Copy as fetch
Paste the entire fetch command into the Fetch Command box in Wiper
Click ▶ Start Cleaning

Method B — Single Channel
Deletes your messages from one specific channel.

Open Discord in browser, navigate to the channel
Press F12 → Network tab → scroll up in chat to trigger a load
Find a request matching:

   messages?limit=50

Right-click → Copy as fetch → paste into Wiper

Optional: Manual Token
If the fetch command doesn't include the Authorization header, paste your Discord token into the Auth Token field. It's masked by default and never stored.

🔐 Security Notes

Your auth token gives full access to your Discord account — treat it like a password
Wiper never logs your token, writes it to disk, or sends it anywhere except Discord's own API
The token field is masked (•••) with an optional Show/Hide toggle
Once you close the app, the token is gone from memory


⏱️ Rate Limiting
Wiper adds 5–8 second random delays between each delete request to stay under Discord's radar. If a 429 Too Many Requests response is received, it waits the exact Retry-After duration before continuing.

📁 Project Structure
wiper.py        # Everything — single-file app
README.md       # This file

📄 License
MIT — do whatever you want, but you're responsible for how you use it.

📸 Features

Guild search mode — finds and deletes all your messages across an entire server
Channel mode — sweeps a specific channel and deletes only your messages
Rate-limit aware — respects Discord's rate limits with automatic retry + jitter delays
Token security — your auth token is never saved to disk, never logged, and never sent anywhere except directly to Discord's API
100% local — no telemetry, no server, no internet traffic except to discord.com


🚀 Requirements

Python 3.8+
No external packages needed (uses only tkinter, urllib, threading, json from stdlib)


▶️ How to Run
bashpython wiper.py

On some Linux distros you may need to install tkinter separately:
bashsudo apt install python3-tk


🛠️ How to Use
Method A — Guild Search (Recommended)
Deletes your messages across an entire server.

Open Discord in Chrome (or any Chromium browser)
Go to any channel in the target server
Press F12 → go to the Network tab
Use Discord's search bar (top-right) → filter by From: You
In the Network tab, find the request matching:

   guilds/.../messages/search?author_id=...

Right-click it → Copy → Copy as fetch
Paste the entire fetch command into the Fetch Command box in Wiper
Click ▶ Start Cleaning

Method B — Single Channel
Deletes your messages from one specific channel.

Open Discord in browser, navigate to the channel
Press F12 → Network tab → scroll up in chat to trigger a load
Find a request matching:

   messages?limit=50

Right-click → Copy as fetch → paste into Wiper

Optional: Manual Token
If the fetch command doesn't include the Authorization header, paste your Discord token into the Auth Token field. It's masked by default and never stored.

---

## 🔐 Security Notes

Your auth token gives full access to your Discord account — treat it like a password
Wiper never logs your token, writes it to disk, or sends it anywhere except Discord's own API
The token field is masked (•••) with an optional Show/Hide toggle
Once you close the app, the token is gone from memory

---

## ⏱️ Rate Limiting
Wiper adds 5–8 second random delays between each delete request to stay under Discord's radar. If a 429 Too Many Requests response is received, it waits the exact Retry-After duration before continuing.

📁 Project Structure
wiper.py        # Everything — single-file app
README.md       # This file

📄 License
MIT — do whatever you want, but you're responsible for how you use it.
