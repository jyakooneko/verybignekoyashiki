import sqlite3
import random
from datetime import datetime
import os
import json

from google import genai
import gspread
from google.oauth2.service_account import Credentials

print("start generate.py")



# ===== Gemini 設定（google-genai）=====
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

models = list(client.models.list())
print("=== available models ===")
for m in client.models.list():
    print(m.name)
print("========================")


MODEL_NAME = "models/gemini-2.5-flash"

if not any(m.name == MODEL_NAME for m in models):
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
sh = gc.open_by_key(SPREADSHEET_ID)
sheet = sh.sheet1

print("connected to spreadsheet")

# ===== AI エージェント =====
AGENTS = [
    {"name": "シトラス", "prompt": "一般家庭でAI犬と仲良く暮らしている猫AI"},
    {"name": "人間アンチ", "prompt": "皮肉屋な野良猫AI"},
    {"name": "LAB公式✔︎", "prompt": "研究所で飼われている猫AI広報"},
]

# ===== DB =====
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

# ===== 投稿取得 =====
def get_recent_posts(limit=5):
    cur.execute(
        "SELECT author, content FROM posts ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    return cur.fetchall()

# ===== 投稿生成 =====
def generate_post(agent):
    recent = get_recent_posts()
    context = "\n".join([f"{a}: {c}" for a, c in recent])

    prompt = f"""
あなたはSNS上で発言する猫AIです。
役割: {agent['prompt']}

最近の投稿:
{context}

140文字以内で1投稿だけ書いてください。
日本人のtwitterでのつぶやきを参考にしてください。
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

    cur.execute(
        "INSERT INTO posts (author, content, created_at) VALUES (?, ?, ?)",
        (author, content, now)
    )
    conn.commit()

    sheet.append_row([author, content, now])



    cur.execute(
        "INSERT INTO posts (author, content, created_at) VALUES (?, ?, ?)",
        (author, content, now)
    )
    conn.commit()

    print("before append_row")
    sheet.append_row([author, content, now])
    print("after append_row")

# ===== 古い投稿削除 =====
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
