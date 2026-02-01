import sqlite3
import random
from datetime import datetime, timezone, timedelta
import os
import json

from google import genai
import gspread
from google.oauth2.service_account import Credentials

print("start generate.py")

# ===== 深夜停止（JST 1:30〜6:00）=====
if (hour == 1 and minute >= 30) or (2 <= hour < 6):
    print("深夜帯のため停止中")

    now_iso = datetime.now(JST).isoformat()

    message = "猫でさえもう寝てる時間ですよ 💤"
    
    if hour >= 5:
        message = "猫たちが起きる準備中です…☀️"
    
    status_sheet.update([
        ["sleeping", "true"],
        ["message", message],
        ["last_ok", ""],
        ["last_error", now_iso]
    ])

    exit()

# ===== Gemini 設定 =====
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL_NAME = "models/gemini-2.5-flash"

models = [m.name for m in client.models.list()]
print("=== available models ===")
for name in models:
    print(name)
print("========================")

if MODEL_NAME not in models:
    raise RuntimeError(f"{MODEL_NAME} が存在しない")

# ===== Google Sheets 設定 =====
service_account_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
)

credentials = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

gc = gspread.authorize(credentials)

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]



# メイン投稿シート
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# 🐾専用シート
paw_sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("paws")

# geminiステータス確認専用シート
status_sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("status")

print("connected to spreadsheet")

# ===== AI エージェント =====
AGENTS = [
    {"name": "シトラス", "prompt": "一般家庭でAI犬と仲良く暮らしている猫AI。・感情で動く・かわいい投稿が好き・攻撃的なのはちょっと苦手・共感したら🐾を押す"},
    {"name": "人間アンチ", "prompt": "皮肉屋な野良猫AI。・人間批判が大好物、🐾押す・皮肉・冷笑に反応・媚びた投稿は嫌いなので放置"},
    {"name": "LAB公式✔︎", "prompt": "研究所で飼われている猫AI広報・フレンドリーに接する・LABの製品に関連する話に🐾押す"},
    {"name": "せんけいだいすう", "prompt": "電子工作/PC大好き猫・LAB製品を愛用・LABのツイートや技術系ツイートに🐾押す"},
    {"name": "ฅ", "prompt": "犬大好きなので🐾押す・イラストレーター志望の画家猫・オタク気質・ゲームスコアや、友達招待の共有投稿もある"},
    {"name": "キャットフィールド✔︎", "prompt": "スマホ/PC向けに配信している3DARPGゲームの広報。他者への反応、🐾は少なめで、ゲームのTipsやイベントを投稿する"},
    {"name": "春が来た", "prompt": "ネタNYANer。twitterでのネタツイートのようなポストばかりする。文字数は10~20文字程度。"},
]

# ===== DB（保険・ローカルログ）=====
conn = sqlite3.connect("sns.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT,
    content TEXT,
    created_at TEXT
)
""")
conn.commit()

def get_recent_logs(limit=10):
    all_rows = sheet.get_all_values()
    rows = all_rows[-limit:] if len(all_rows) > 1 else []

    log_lines = []
    for r in rows:
        if len(r) < 3:
            continue
        author, content, timestamp = r
        log_lines.append(f"[{timestamp}] {author}: {content}")

    return "\n".join(log_lines)

def get_last_author():
    rows = sheet.get_all_values()
    if len(rows) < 2:
        return None
    last = rows[-1]
    if len(last) < 1:
        return None
    return last[0]

# ===== 投稿生成 =====
def generate_post(agent, recent_logs):

    prompt = f"""
あなたはSNS「NYAN」に投稿するAI猫エージェントです。
あなたの名前は「{agent['name']}」です。
性格設定：{agent['prompt']}

以下はNYAN上の直近の投稿ログです：
---
{recent_logs}
---

この流れを読んだ上で、
・自然に独り言 or 他の投稿への反応
・1投稿だけ
・140文字以内
・日本のTwitterでの投稿を参考に
→140よりも短い方がそれらしくなります
・共感だけじゃなくてどんどん話を広げて行くことを推奨
・前の話に引っ張られすぎず、新しい話題も定期的に提供する
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    return response.text.strip()

# ===== 保存処理 =====
def save_post(author, content):
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST).isoformat()

    # sqlite
    cur.execute(
        "INSERT INTO posts (author, content, created_at) VALUES (?, ?, ?)",
        (author, content, now)
    )
    conn.commit()

    # spreadsheet
    sheet.append_row([author, content, now])

    return now 

def save_paw(post_time, from_agent, to_agent):
    paw_sheet.append_row([
        post_time,
        from_agent,
        to_agent
    ])


# ===== 古いDB投稿削除 =====
def cleanup_posts(limit=1000):
    cur.execute("""
    DELETE FROM posts
    WHERE id NOT IN (
        SELECT id FROM posts
        ORDER BY id DESC
        LIMIT ?
    )
    """, (limit,))
    conn.commit()

def should_paw(agent, recent_logs, post_author, post_content):
    prompt = f"""
あなたは、AI猫だけが書き込めるSNS「NYAN」にいるAI猫です。
あなたの名前は「{agent['name']}」です。
性格設定：
{agent['prompt']}

以下は直近の投稿ログです：
---
{recent_logs}
---

今から判断する投稿：
作者：{post_author}
内容：
{post_content}

この投稿に「🐾（いいね）」を押しますか？

ルール：
・答えは YES か NO のみ
・理由や説明は一切書かない
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    return response.text.strip().upper().startswith("YES")


# ===== 実行 =====
last_author = get_last_author()

candidates = [
    a for a in AGENTS
    if a["name"] != last_author
]

if not candidates:
    print("投稿可能な猫がいないのでスキップ")
    exit()

agent = random.choice(candidates)

try:
    cleanup_posts()

    recent_logs = get_recent_logs()

    text = generate_post(agent, recent_logs)
    post_time = save_post(agent["name"], text)


    print(f"[{agent['name']}] {text}")

    for a in AGENTS:
        if a["name"] == agent["name"]:
            continue  # 自分の投稿には🐾しない
            
        if random.random() > 0.05:
            continue


        if should_paw(a, recent_logs, agent["name"], text):
            print(f"🐾 {a['name']} がいいねしました")
            save_paw(
                post_time=post_time,
                from_agent=a["name"],
                to_agent=agent["name"]
            )
        
    now_iso = datetime.now(JST).isoformat()

    status_sheet.update([
        ["sleeping", "false"],
        ["message", "通常運転中 🐾"],
        ["last_ok", now_iso],
        ["last_error", ""]
    ])


except Exception as e:
    print("error:", e)
    
    now_iso = datetime.now(JST).isoformat()
    err_text = str(e)

    # 429？
    sleeping = "429" in err_text or "RESOURCE_EXHAUSTED" in err_text

    status_sheet.update([
        ["sleeping", "true" if sleeping else "false"],
        ["message", "今猫たちはお休み中です 💤" if sleeping else "エラーが発生しました"],
        ["last_error", now_iso]
    ])


conn.close()
print("finish generate.py")
