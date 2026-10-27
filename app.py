import os
import csv
import sqlite3
import threading
from datetime import datetime

import discord
from flask import Flask, render_template, jsonify
from openai import OpenAI


# =========================================================
# Environment variables
# =========================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

client_ai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# =========================================================
# Flask app
# =========================================================
app = Flask(__name__)


# =========================================================
# Discord bot setup
# =========================================================
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
discord_client = discord.Client(intents=intents)


# =========================================================
# FAQ knowledge base
# =========================================================
faq_data = {
    "when is round 1": "Round 1 starts May 29th.",
    "how to register": "You can register on our portal.",
    "how do i know if i am a finalist?": "Finalists will be announced after the team formation period ends on April 29th. We will be reaching out via email to notify all finalists.",
    "when will scores be released?": "Scores for Preliminary Online Rounds will be released within 48 hours after each exam ends. Scores will be available directly on the Testing Portal.",
    "i missed an exam what should i do?": "Unfortunately, there is no way to make up the exam if you miss the exam period. However, we understand that extraordinary circumstances can occur. If you believe such a situation prevented you from taking the exam, please reach out to us.",
    "what to do if i have a technical issue?": "If you experience a technical issue during the exam, please write your answers on paper and take a screenshot of your technical issue. Send both your written answers and proof of the issue to us via email. We will then review your case after the exam period and reach back out to you. Please note: You must submit your handwritten answers as well as proof of the technical issue.",
    "when is the exam open?": "Participants will have a window of 24 hours in which to complete the exam. After they open the exam, they will have 75 minutes to complete it. The exam must be started and completed within the 24-hour window. Participants are only able to take the exam one time within the 24-hour period.",
    "who is eligible for the olympiad?": "Participants must be between grades 8-12 (or Year 9-13 in the UK). Participants must also create an account and complete the email verification process. Users must verify their email to be able to register. Users may be asked to verify their student status with school ID verification.",
    "how can i form a team?": "Step 1: Gather a team of 2 to 4 members. Step 2: Assign a team leader. Step 3: Collect everyone's names and emails used for registration. Step 4: The team leader will register their team once the Team Formation period begins.",
    "how can i get involved?": "Please visit the official Get Involved page on the ILO website.",
    "how do i get my certificate for the olympiad?": "When the Final Round has concluded, we will send out certificates to all who qualify.",
    "how is the olympiad structured?": "The ILO starts with 3 preliminary rounds which are taken completely online through the test portal. From the results of the preliminary rounds, finalists will be determined, and those finalists will be invited to participate in the final in-person round at Stanford University.",
    "how do i pay for registration?": "Registration payment can be found in the test portal after you have created an account. Make sure that you have verified your account through the email address provided; otherwise, the payment option will not appear.",
    "can you help with my visa?": "Finalists from outside of the United States are responsible for securing their own visas for the Final Round. However, we can assist by providing documentation stating your participation in the ILO Final Round. Please reach out via email if this applies."
}


# =========================================================
# Database helpers
# =========================================================
DB_PATH = "database.db"
CSV_LOG_PATH = "chat_log.csv"


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            reply TEXT NOT NULL,
            is_replied INTEGER NOT NULL
        )
    """)
    con.commit()
    return con


def setup_database():
    con = init_db()
    con.close()


def log_to_db(username, message_text, reply_text, is_replied):
    con = init_db()
    con.execute(
        """
        INSERT INTO chats (ts, username, message, reply, is_replied)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            username,
            message_text,
            reply_text,
            1 if is_replied else 0
        )
    )
    con.commit()
    con.close()


def log_to_csv(username, message_text, reply_text, is_replied):
    file_exists = os.path.isfile(CSV_LOG_PATH)
    with open(CSV_LOG_PATH, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["timestamp", "username", "message", "reply", "is_replied"])

        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            username,
            message_text,
            reply_text,
            1 if is_replied else 0
        ])


def get_stats():
    con = init_db()
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM chats")
    total = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM chats WHERE is_replied = 1")
    answered = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM chats WHERE is_replied = 0")
    fallback = cur.fetchone()[0] or 0

    con.close()
    return total, answered, fallback


def get_recent_chats(limit=8):
    con = init_db()
    cur = con.cursor()
    cur.execute("""
        SELECT ts, username, message, reply, is_replied
        FROM chats
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    con.close()
    return rows


def get_top_users(limit=5):
    con = init_db()
    cur = con.cursor()
    cur.execute("""
        SELECT username, COUNT(*) AS cnt
        FROM chats
        GROUP BY username
        ORDER BY cnt DESC, username ASC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    con.close()
    return rows


def get_message_volume_by_day(limit=7):
    con = init_db()
    cur = con.cursor()
    cur.execute("""
        SELECT substr(ts, 1, 10) AS day, COUNT(*) AS cnt
        FROM chats
        GROUP BY day
        ORDER BY day DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    con.close()

    rows = list(rows)[::-1]
    labels = [row["day"] for row in rows]
    values = [row["cnt"] for row in rows]
    return labels, values


def get_dashboard_data():
    total, answered, fallback = get_stats()
    resolution_rate = round((answered / total) * 100, 1) if total else 0.0

    daily_labels, daily_values = get_message_volume_by_day(limit=7)
    top_users = get_top_users(limit=5)
    recent_chats = get_recent_chats(limit=8)

    faq_category_labels = [
        "Exam",
        "Registration",
        "Team",
        "Support",
        "Results",
        "Final Round"
    ]
    faq_category_values = [3, 2, 1, 3, 2, 3]

    return {
        "total_messages": total,
        "answered_messages": answered,
        "fallback_messages": fallback,
        "resolution_rate": resolution_rate,
        "faq_count": len(faq_data),
        "daily_labels": daily_labels,
        "daily_values": daily_values,
        "faq_category_labels": faq_category_labels,
        "faq_category_values": faq_category_values,
        "top_users": [dict(row) for row in top_users],
        "recent_chats": [dict(row) for row in recent_chats]
    }


# =========================================================
# GPT reply helper
# =========================================================
def generate_bot_reply(user_msg):
    user_msg_clean = user_msg.lower().strip()

    greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
    if user_msg_clean in greetings:
        return "Hello. How can I help you with the International Logic Olympiad?", True

    if not client_ai:
        return "Thank you for your question. A support team will get back to you soon.", False

    system_prompt = f"""
Answer the user query only based on this FAQ data:

{faq_data}

You must follow these rules:
1. Do not ask follow-up questions.
2. If the question cannot be answered based on the FAQ data, respond exactly with:
Thank you for your question. A support team will get back to you soon.
3. If the question is a greeting, respond with a short greeting.
4. Keep the answer clear and concise.
"""

    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg_clean}
            ]
        )

        reply = response.choices[0].message.content.strip()
        is_replied = reply != "Thank you for your question. A support team will get back to you soon."
        return reply, is_replied

    except Exception:
        return "Thank you for your question. A support team will get back to you soon.", False


# =========================================================
# Discord events
# =========================================================
@discord_client.event
async def on_ready():
    print(f"Discord bot is online as {discord_client.user}")


@discord_client.event
async def on_message(message):
    if message.author == discord_client.user:
        return

    user_msg = message.content.strip().lower()

    if user_msg == "!exam_start":
        await message.channel.send("Round 1 starts on May 29th.")
        return

    if user_msg == "!stats":
        total, answered, fallback = get_stats()
        reply = (
            "--- General Statistics ---\n"
            f"- Total messages: {total}\n"
            f"- Answered by AI: {answered}\n"
            f"- Fallback replies: {fallback}"
        )
        await message.channel.send(reply)
        return

    reply, is_replied = generate_bot_reply(message.content)

    await message.channel.send(reply)
    log_to_db(str(message.author), message.content, reply, is_replied)
    log_to_csv(str(message.author), message.content, reply, is_replied)


def run_discord_bot():
    if not DISCORD_BOT_TOKEN:
        print("DISCORD_BOT_TOKEN is missing. Discord bot was not started.")
        return

    try:
        discord_client.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"Discord bot failed to start: {e}")


# =========================================================
# Flask routes
# =========================================================
@app.route("/")
def index():
    dashboard = get_dashboard_data()
    return render_template("index.html", **dashboard)


@app.route("/story/new")
def story_new():
    return render_template("story_new.html")


@app.route("/api/dashboard-stats")
def api_dashboard_stats():
    return jsonify(get_dashboard_data())


# =========================================================
# Main
# =========================================================
if __name__ == "__main__":
    setup_database()

    discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
    discord_thread.start()

    app.run(debug=True, host="0.0.0.0", port=8080)