
import requests
import time

# 🔑 Дані
API_KEY = 'AIzaSyB1GlNtoCX2d2BM67n20hFeOqJ51nMZvnM'
CHANNEL_ID = 'UCcBeq64BydUvdA-kZsITNlg'  # ID YouTube-каналу
BOT_TOKEN = '8041256909:AAGjruzEE61q_H4R5zAwpTf53Peit37lqEg'
CHAT_ID = '@testbotika12'  # або ID (наприклад -1001234567890)

TIKTOK_USERNAME = 'top_gamer_qq'

# Статуси
was_live_youtube = False
was_live_tiktok = False

def check_youtube():
    url = f'https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={CHANNEL_ID}&type=video&eventType=live&key={API_KEY}'
    response = requests.get(url).json()
    
    items = response.get('items', [])
    if items:
        video_id = items[0]['id']['videoId']
        title = items[0]['snippet']['title']
        return f'https://www.youtube.com/watch?v={video_id}', title
    return None, None

def check_tiktok():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        url = f'https://www.tiktok.com/@{TIKTOK_USERNAME}'
        response = requests.get(url, headers=headers)
        if 'LIVE' in response.text or '"isLive":true' in response.text:
            return f'https://www.tiktok.com/@{TIKTOK_USERNAME}/live'
    except Exception as e:
        print("TikTok помилка:", e)
    return None

def send_message(text):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    data = {'chat_id': CHAT_ID, 'text': text}
    requests.post(url, data=data)

# 🔁 Основний цикл
while True:
    try:
        # YouTube
        link, title = check_youtube()
        if link and not was_live_youtube:
            send_message(f"🔴 YouTube стрім почався!\n🎥 {title}\n👉 {link}")
            was_live_youtube = True
        elif not link:
            was_live_youtube = False

        # TikTok
        tiktok_live = check_tiktok()
        if tiktok_live and not was_live_tiktok:
            send_message(f"🎥 TikTok стрім почався!\n👉 {tiktok_live}")
            was_live_tiktok = True
        elif not tiktok_live:
            was_live_tiktok = False

    except Exception as e:
        print("Помилка:", e)

    time.sleep(60)