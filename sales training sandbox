oimport streamlit as st
import json
import sqlite3
from pathlib import Path
from openai import OpenAI
from datetime import datetime

# CONFIG
PROSPECTS_FILE = "data/prospects.json"
DB_FILE = str(Path(__file__).parent / "leaderboard.db")  # Persistent path
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
    c.execute("INSERT INTO leaderboard (name, score, timestamp) VALUES (?, ?, ?)", 
              (name, score, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def add_chat_to_db(name, chat_text):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (name, chat, timestamp) VALUES (?, ?, ?)", 
              (name, chat_text, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def store_performance_summary(name, avg_score, summary):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO performance_reports (name, avg_score, summary, timestamp) VALUES (?, ?, ?, ?)",
              (name, avg_score, summary, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_top_scores(limit=10):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name, score FROM leaderboard ORDER BY score DESC, timestamp ASC LIMIT ?", (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_all_chats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name, chat, timestamp FROM chat_history ORDER BY timestamp DESC")
    results = c.fetchall()
    conn.close()
    return results

def get_user_feedback_summary(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT score FROM leaderboard WHERE name = ?", (name,))
    scores = [row[0] for row in c.fetchall()]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    c.execute("SELECT chat FROM chat_history WHERE name = ? ORDER BY timestamp DESC LIMIT 5", (name,))
    recent_chats = c.fetchall()
    transcript_blocks = "\n\n".join(chat[0] for chat in recent_chats)

    prompt = f"""
You are a sales performance coach. Analyze this user's last 5 sales chats and summarize:
- Their top 2 strengths
- Their top 2 mistakes
Return your response in plain language.

Chat transcripts:
{transcript_blocks}
    """

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": prompt}]
    )
    feedback_summary = response.choices[0].message.content.strip()
    return avg_score, feedback_summary

# ---------------- APP ----------------
init_db()

if "history" not in st.session_state:
    st.session_state.history = []
if "selected_prospect" not in st.session_state:
    st.session_state.selected_prospect = None
if "trainee_name" not in st.session_state:
    st.session_state.trainee_name = ""

st.set_page_config(page_title="Grass Nerds Sales Training Chatbot", layout="wide")
st.markdown("## 🗨️ Grass Nerds Sales Training Chatbot")

# Sidebar: trainee info
with st.sidebar:
    st.header("Trainee Info")
    st.session_state.trainee_name = st.text_input("Enter your name")

# Load prospects and select
prospects = json.loads(Path(PROSPECTS_FILE).read_text())
prospect_names = [f"{p['name']} ({p['role']})" for p in prospects]
selected_name = st.selectbox("Select Prospect", prospect_names)
selected_prospect = next((p for p in prospects if f"{p['name']} ({p['role']})" == selected_name), None)
st.session_state.selected_prospect = selected_prospect

# Show persona
st.markdown(
    f"""
    <div style="border:1px solid #ddd;border-radius:10px;padding:1rem;background:#f8f8f8;">
        <strong>Persona:</strong> {selected_prospect['name']} ({selected_prospect['role']})
    </div>
    """, unsafe_allow_html=True
)

# Display chat
for speaker, text in st.session_state.history:
    icon = "💬" if speaker == "sales_rep" else "🌱"
    label = "You" if speaker == "sales_rep" else "Prospect"
    st.chat_message(label, avatar=icon).write(text)

user_input = st.chat_input("💬 Your message")
if user_input:
    st.session_state.history.append(("sales_rep", user_input))

    prompt = (
        f"You are '{selected_prospect['name']}', a {selected_prospect['role']} in a sales training simulation. "
        f"Your hidden pain points are: {selected_prospect.get('pain_points', 'no pain points provided')}. "
        f"Only reveal them if the trainee asks good discovery questions. If the trainee reveals your pain point and asks you to use their service in any way, say that you are ready to use their service and that you are excited. Be realistic, friendly, and natural."
    )
    messages = [{"role": "system", "content": prompt}]
    for speaker, text in st.session_state.history:
        role = "assistant" if speaker == "prospect" else "user"
        messages.append({"role": role, "content": text})

    response = client.chat.completions.create(model=MODEL_NAME, messages=messages)
    reply = response.choices[0].message.content.strip()
    st.session_state.history.append(("prospect", reply))
    st.chat_message("Prospect", avatar="🌱").write(reply)

# Sidebar: scoring, history, summary
with st.sidebar:
    st.header("Score")

    if st.button("End Chat & Generate Score"):
        name = st.session_state.trainee_name.strip()
        if not name:
            st.warning("Please enter your name.")
        else:
            transcript = "\n".join(
                [f"{'Trainee' if s == 'sales_rep' else 'Prospect'}: {t}" for s, t in st.session_state.history]
            )
            eval_prompt = f"""
You are a sales coach. Return ONLY raw JSON — no formatting.
Evaluate this sales chat:
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
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "system", "content": eval_prompt}]
            )
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.strip("`").strip()
                if text.startswith("json"):
                    text = text[4:].strip()
            eval_result = json.loads(text)

            total_score = sum([
                eval_result['rapport'],
                eval_result['discovery'],
                eval_result['solution_alignment'],
                eval_result['objection_handling'],
                eval_result['closing'],
                eval_result['positivity']
            ]) * (100 / 60)

            add_score_to_db(name, int(total_score))
            add_chat_to_db(name, transcript)

            st.success(f"🏆 Score: {int(total_score)}/100")
            st.write("### Feedback")
            for k, v in eval_result['feedback'].items():
                st.write(f"**{k.capitalize()}**: {v}")

    if st.button("Start New Prospect"):
        st.session_state.history = []

    st.write("### 🏅 Leaderboard")
    scores = get_top_scores()
    for entry in scores:
        st.write(f"{entry[0]}: {entry[1]}")

    st.write("### 📜 View Past Chats")
    all_chats = get_all_chats()
    chat_options = [f"{name} - {ts}" for name, _, ts in all_chats]
    selected_chat = st.selectbox("Choose a chat", chat_options)
    for name, chat, ts in all_chats:
        if f"{name} - {ts}" == selected_chat:
            with st.expander(f"Transcript from {ts}", expanded=True):
                st.code(chat)

    st.write("### 📈 View Performance Summary")
    if st.button("Generate Summary"):
        name = st.session_state.trainee_name.strip()
        if not name:
            st.warning("Please enter your name first.")
        else:
            avg, summary = get_user_feedback_summary(name)
            store_performance_summary(name, avg, summary)
            st.success("✅ Summary generated and saved!")
            st.markdown(f"**📊 Avg Score:** {avg}/100")
            st.markdown(summary)
