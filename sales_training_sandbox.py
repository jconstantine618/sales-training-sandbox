import streamlit as st
import json
import sqlite3
from pathlib import Path
from openai import OpenAI
from datetime import datetime

# ---------------- CONFIG ----------------
PROSPECTS_FILE = "data/prospects.json"
DB_FILE = str(Path(__file__).parent / "leaderboard.db")
MODEL_NAME = "gpt-4o"
MAX_SCORE = 100

# Load OpenAI API key from Streamlit Secrets
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------- DB FUNCTIONS ----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS leaderboard (name TEXT, score INTEGER, timestamp TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS chat_history (name TEXT, chat TEXT, timestamp TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS performance_reports (name TEXT, avg_score REAL, summary TEXT, timestamp TEXT)")
    conn.commit()
    conn.close()

def add_score_to_db(name, score):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO leaderboard (name, score, timestamp) VALUES (?, ?, ?)",
        (name, score, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def add_chat_to_db(name, chat_text):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO chat_history (name, chat, timestamp) VALUES (?, ?, ?)",
        (name, chat_text, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def store_performance_summary(name, avg_score, summary):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO performance_reports (name, avg_score, summary, timestamp) VALUES (?, ?, ?, ?)",
        (name, avg_score, summary, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_top_scores(limit=10):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT name, score FROM leaderboard ORDER BY score DESC, timestamp ASC LIMIT ?",
        (limit,)
    )
    results = c.fetchall()
    conn.close()
    return results

def get_all_chats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT name, chat, timestamp FROM chat_history ORDER BY timestamp DESC"
    )
    results = c.fetchall()
    conn.close()
    return results

def get_user_feedback_summary(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT score FROM leaderboard WHERE name = ?", (name,))
    scores = [row[0] for row in c.fetchall()]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    c.execute(
        "SELECT chat FROM chat_history WHERE name = ? ORDER BY timestamp DESC LIMIT 5",
        (name,)
    )
    recent = c.fetchall()
    transcript_blocks = "\n\n".join(chat[0] for chat in recent)

    prompt = f"""
You are a sales performance coach. Analyze this user's last 5 sales chats and summarize:
- Their top 2 strengths
- Their top 2 mistakes
Return in plain language.

Chat transcripts:
{transcript_blocks}
    """

    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": prompt}]
    )
    return avg_score, resp.choices[0].message.content.strip()

# ---------------- APP LAYOUT ----------------
init_db()

# Initialize session state
if "history" not in st.session_state:
    st.session_state.history = []
if "selected_prospect" not in st.session_state:
    st.session_state.selected_prospect = None
if "trainee_name" not in st.session_state:
    st.session_state.trainee_name = ""

st.set_page_config(page_title="Grass Nerds Sales Training Chatbot", layout="wide")
st.markdown("## 🗨️ Grass Nerds Sales Training Chatbot")

# Sidebar: Trainee Info
with st.sidebar:
    st.header("Trainee Info")
    st.session_state.trainee_name = st.text_input("Enter your name")

# ---------------- Prospect Selection ----------------
prospects = json.loads(Path(PROSPECTS_FILE).read_text())
# Build labels: Company — Name (Role) — Industry
labels = [
    f"{p['company']} — {p['name']} ({p['role']}) — {p['industry']}"
    for p in prospects
]
selected_label = st.selectbox("Select Prospect", labels)
idx = labels.index(selected_label)
st.session_state.selected_prospect = prospects[idx]

# Show Persona Card
p = st.session_state.selected_prospect
st.markdown(
    f"""
<div style="border:1px solid #ddd; border-radius:10px; padding:1rem; background:#f8f8f8;">
  <strong>Persona:</strong> {p['company']} — {p['name']} ({p['role']}) — {p['industry']}
</div>
""",
    unsafe_allow_html=True
)

# ---------------- Chat Interface ----------------
for speaker, text in st.session_state.history:
    icon = "💬" if speaker == "sales_rep" else "🌱"
    label = "You" if speaker == "sales_rep" else "Prospect"
    st.chat_message(label, avatar=icon).write(text)

user_input = st.chat_input("💬 Your message")
if user_input:
    st.session_state.history.append(("sales_rep", user_input))

    # Build LLM prompt for prospect simulation
    prompt = (
        f"You are '{p['name']}', a {p['role']} at {p['company']} ({p['industry']}). "
        f"Your hidden pain points: {p.get('pain_points','')}. "
        "Reveal them only if the trainee asks good discovery questions. "
        "If they uncover your pain and propose your solution, respond that you're ready and excited."
    )
    messages = [{"role": "system", "content": prompt}]
    for spk, txt in st.session_state.history:
        role = "assistant" if spk == "prospect" else "user"
        messages.append({"role": role, "content": txt})

    resp = client.chat.completions.create(model=MODEL_NAME, messages=messages)
    reply = resp.choices[0].message.content.strip()
    st.session_state.history.append(("prospect", reply))
    st.chat_message("Prospect", avatar="🌱").write(reply)

# ---------------- Sidebar: Scoring & History ----------------
with st.sidebar:
    st.header("Score & History")

    if st.button("End Chat & Generate Score"):
        name = st.session_state.trainee_name.strip()
        if not name:
            st.warning("Please enter your name first.")
        else:
            transcript = "\n".join(
                f"{'Trainee' if s=='sales_rep' else 'Prospect'}: {t}"
                for s, t in st.session_state.history
            )
            eval_prompt = f"""
You are a sales coach. Return ONLY raw JSON.
Evaluate this chat:
{{
  "rapport": 0-10,
  "discovery": 0-10,
  "solution_alignment": 0-10,
  "objection_handling": 0-10,
  "closing": 0-10,
  "positivity": 0-10,
  "dale_carnegie_principles": 0-5,
  "feedback": {{
    "rapport": "...",
    "discovery": "...",
    "solution_alignment": "...",
    "objection_handling": "...",
    "closing": "...",
    "positivity": "...",
    "dale_carnegie_principles": "..."
  }}
}}
Chat:
{transcript}
"""
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "system", "content": eval_prompt}]
            )
            text = resp.choices[0].message.content.strip()
            # strip markdown/fences
            if text.startswith("```"):
                text = text.strip("`").split("json",1)[-1].strip()
            result = json.loads(text)

            # compute total out of 100
            total = sum([
                result['rapport'],
                result['discovery'],
                result['solution_alignment'],
                result['objection_handling'],
                result['closing'],
                result['positivity']
            ]) * (100 / 60)
            score = int(total)

            add_score_to_db(name, score)
            add_chat_to_db(name, transcript)

            st.success(f"🏆 Score: {score}/100")
            st.write("### Feedback")
            for k, v in result['feedback'].items():
                st.write(f"**{k.capitalize()}**: {v}")

    if st.button("Start New Prospect"):
        st.session_state.history = []

    st.write("### 🏅 Leaderboard")
    for nm, sc in get_top_scores():
        st.write(f"{nm}: {sc}")

    st.write("### 📜 Past Chats")
    all_chats = get_all_chats()
    chat_labels = [f"{n} — {ts}" for n, _, ts in all_chats]
    sel = st.selectbox("Choose a chat", chat_labels)
    for nm, ch, ts in all_chats:
        if f"{nm} — {ts}" == sel:
            with st.expander(f"Transcript from {ts}", expanded=True):
                st.code(ch)

    st.write("### 📈 Performance Summary")
    if st.button("Generate Summary"):
        name = st.session_state.trainee_name.strip()
        if not name:
            st.warning("Enter your name first.")
        else:
            avg, summary = get_user_feedback_summary(name)
            store_performance_summary(name, avg, summary)
            st.success("✅ Summary generated!")
            st.markdown(f"**📊 Avg Score:** {avg}/100")
            st.markdown(summary)
