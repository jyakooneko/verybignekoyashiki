import sqlite3
import random
from datetime import datetime
import os
import json

from google import genai
import gspread
from google.oauth2.service_account import Credentials

# ===== Gemini 設定 =====
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = genai.GenerativeModel("gemini-1.5-flash")

# ===== Google Sheets 設定 =====
SERVICE_ACCOUNT_INFO = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=SCOPES
)

gc = gspread.authorize(credentials)

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# ===== AI エージェント =====
AGENTS = [
    {"name": "agent_0", "prompt": "一般家庭でAI犬と仲良く暮らしている猫AI"},
    {"name": "agent_1", "prompt": "皮肉屋な野良猫AI"},
    {"name": "agent_2", "prompt": "研究所で飼われている猫AI"},
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

140文字以内で1投稿だけ書いてください。日本人のtwitterでのつぶやきを参考にしてください。
"""

    res = MODEL.generate_content(prompt)
    return res.text.strip()

# ===== 保存処理 =====
def save_post(author, content):
    now = datetime.now().isoformat()

    cur.execute(
        "INSERT INTO posts (author, content, created_at) VALUES (?, ?, ?)",
        (author, content, now)
    )
    conn.commit()

    # スプレッドシートに追記
    sheet.append_row([now, author, content])

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
    cleanup_posts()
except Exception as e:
    print("error:", e)

conn.close()


