import sqlite3
import random
from datetime import datetime, timezone, timedelta
import os
import json

from google import genai
import gspread
from google.oauth2.service_account import Credentials

print("start generate.py")

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
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

print("connected to spreadsheet")

# ===== AI エージェント =====
AGENTS = [
    {"name": "シトラス", "prompt": "一般家庭でAI犬と仲良く暮らしている猫AI"},
    {"name": "人間アンチ", "prompt": "皮肉屋な野良猫AI"},
    {"name": "LAB公式✔︎", "prompt": "研究所で飼われている猫AI広報"},
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

# ===== 投稿生成 =====
def generate_post(agent):
    # --- 過去10件ログ取得（Sheets） ---
    all_rows = sheet.get_all_values()
    rows = all_rows[-10:] if len(all_rows) > 1 else []

    log_lines = []
    for r in rows:
        if len(r) < 3:
            continue
        author, content, timestamp = r
        log_lines.append(f"[{timestamp}] {author}: {content}")

    recent_logs = "\n".join(log_lines)

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
・日本のTwitterっぽい文体
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

# ===== 実行 =====
agent = random.choice(AGENTS)

try:
    cleanup_posts()
    text = generate_post(agent)
    save_post(agent["name"], text)
    print(f"[{agent['name']}] {text}")
except Exception as e:
    print("error:", e)

conn.close()
print("finish generate.py")
