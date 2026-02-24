import requests
from datetime import datetime

API_KEY = os.environ["API_KEY"]
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

def send_test_message():

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    message = f"""
━━━━━━━━━━━━━━━━━━
🤖 Bot Activated & Connected ✅
🔗 Status: Online
🕒 Time: {datetime.now().strftime('%H:%M:%S')} IST
━━━━━━━━━━━━━━━━━━
"""

    for chat_id in CHAT_IDS:
        response = requests.post(url, data={
            "chat_id": chat_id,
            "text": message
        })

        if response.status_code == 200:
            print(f"✅ Sent to {chat_id}")
        else:
            print(f"❌ Failed for {chat_id}", response.text)

# Run test
send_test_message()
