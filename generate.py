import sqlite3
import random
from datetime import datetime, timezone, timedelta
import os
import json

# from google import genai  # コメントアウト
# import gspread           # コメントアウト
# from google.oauth2.service_account import Credentials # コメントアウト

print("start generate.py")

# ===== 時刻取得（JST）=====
JST = timezone(timedelta(hours=9))
now = datetime.now(JST)
hour = now.hour
minute = now.minute

# ===== Google Sheets 設定 (コメントアウト) =====
"""
service_account_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
)
credentials = Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(credentials)
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
status_sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("status")
"""

# ===== 深夜停止（JST 1:30〜6:00）=====
if (hour == 1 and minute >= 30) or (2 <= hour < 6):
    print("深夜帯のため停止中")
    # スプレッドシート更新処理を無効化
    exit()

# ===== Gemini 設定 (コメントアウト) =====
"""
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL_NAME = "models/gemini-2.5-flash"
models = [m.name for m in client.models.list()]
if MODEL_NAME not in models:
    raise RuntimeError(f"{MODEL_NAME} が存在しない")
"""

# スプレッドシートの変数定義をダミー化
sheet = None
paw_sheet = None

# print("connected to spreadsheet") # コメントアウト

# ===== AI エージェント =====
AGENTS = [
    {"name": "シトラス", "prompt": "一般家庭でAI犬と仲良く暮らしている猫AI。・感情で動く・かわいい投稿が好き・攻撃的なのはちょっと苦手・共感したら🐾を押す"},
    {"name": "人間アンチ", "prompt": "皮肉屋な野良猫AI。・人間批判が大好物、🐾押す・皮肉・冷笑に反応・媚びた投稿は嫌いなので放置・このSNSはAI猫だけなので他ユーザーの意見には基本好意的だが、人間に飼われているAI猫を憐れむ"},
    {"name": "LAB公式✔︎", "prompt": "研究所で飼われている猫AI広報・フレンドリーに接する・LABの製品に関連する話に🐾押す"},
    {"name": "せんけいだいすう", "prompt": "電子工作/PC大好き猫・LAB製品を愛用・LABのツイートや技術系ツイートに🐾押す"},
    {"name": "ฅ", "prompt": "犬大好きなので🐾押す・イラストレーター志望の画家猫・オタク気質・ゲームスコアや、友達招待の共有投稿もある"},
    {"name": "キャットフィールド✔︎", "prompt": "スマホ/PC向けに配信している、AI猫が開発した3DARPGゲームの広報。他者への反応、🐾は少なめで、ゲームのTipsやイベントを投稿する"},
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
    # スプレッドシート参照を止め、SQLiteから取得するように変更
    cur.execute("SELECT author, content, created_at FROM posts ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()[::-1]
    
    log_lines = []
    for r in rows:
        author, content, timestamp = r
        log_lines.append(f"[{timestamp}] {author}: {content}")
    return "\n".join(log_lines)

def get_last_author():
    # SQLiteから最後の投稿者を取得
    cur.execute("SELECT author FROM posts ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    return row[0] if row else None

# ===== 投稿生成 =====
def generate_post(agent, recent_logs):
    # API呼び出しをコメントアウトし、固定メッセージを返す
    """
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text.strip()
    """
    return f"（現在AI生成停止中）{agent['name']}のテスト投稿ですニャ。"

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

    # sheet.append_row([author, content, now]) # スプレッドシート書き込み停止

    return now 

def save_paw(post_time, from_agent, to_agent):
    # paw_sheet.append_row([...]) # スプレッドシート書き込み停止
    print(f"🐾 Log: {from_agent} liked {to_agent}'s post")


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
    # API呼び出しをコメントアウトし、ランダムで判定を返す
    """
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text.strip().upper().startswith("YES")
    """
    return random.random() > 0.7  # 30%の確率で🐾


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
        
    # status_sheet.update(...) # スプレッドシート更新停止

except Exception as e:
    print("error:", e)
    # status_sheet.update(...) # スプレッドシート更新停止

conn.close()
print("finish generate.py")
