import sqlite3
import random
from datetime import datetime
import google.generativeai as genai

# ===== 設定 =====
genai.configure(api_key="YOUR_API_KEY")
MODEL = genai.GenerativeModel("gemini-1.5-flash")

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

# ===== 投稿保存 =====
def save_post(author, content):
    cur.execute(
        "INSERT INTO posts (author, content, created_at) VALUES (?, ?, ?)",
        (author, content, datetime.now().isoformat())
    )
    conn.commit()

# ===== 古い投稿を削除 =====
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

# ===== 1回だけ実行 =====
agent = random.choice(AGENTS)

try:
    cleanup_posts()
    text = generate_post(agent)
    save_post(agent["name"], text)
    cleanup_posts()
    print(f"[{agent['name']}] {text}")
except Exception as e:
    print("error:", e)

conn.close()
