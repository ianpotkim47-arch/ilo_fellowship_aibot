import discord
from openai import OpenAI
import csv # comma-seperated-values --> file type of data file.
import os
from datetime import datetime
import sqlite3 # for connecting our app to DB.

client_ai = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", ""))


intents = discord.Intents.default()
intents.messages = True
intents.message_content =True
client = discord.Client(intents=intents)

faq_data = {
    "when is round 1": "Round 1 starts May 29th",
    "how to register": "you can register on our portal",
    "how do I know if I am a finalist?": "Finalists will be announced after the team formation period ends on April 29th. We will be reaching out via email to notify all finalists.",
    "when will scores be released?" : "Scores for Preliminary Online Rounds will be released within 48 hours after each exam ends. Scores will be available directly on the Testing Portal.",
    "I missed an exam what should I do?" : "Unfortunately, there is no way to make up the exam if you miss the exam period. However, we understand that extraordinary circumstances can occur. If you believe such a situation prevented you from taking the exam, please reach out to us.",
    "what to do if I have a technical issue?" : "If you experience a technical issue during the exam, please write your answers on paper and take a screenshot of your technical issue. Send both your written answers and proof of the issue to us via email. We will then review your case after the exam period and reach back out to you. Please note: You **MUST** submit your handwritten answers as well as proof of the technical issue.",
    "when is the exam open?" : "Participants will have a window of 24 hours in which to complete the exam. After they open the exam, they will have 75 minutes to complete it. The exam must be started and completed within the 24-hour window. Participants are only able to take the exam ONE TIME within the 24-hour period.",
    "who is eligible for the olympiad?" : "Participants MUST BE between grades 8 - 12 (or Year 9-13 in the UK). Participants must also create an account and complete the email verification process Users must verify their email to be able to register *Users may be asked to verify their student status with School ID verification",
    "how can I form a team?" : "Step 1: Gather a team of 2 to 4 members Step 2: Assign a team leader Step 3: Collect all everyones' names and emails used for registration Step 4: Team leader will register their team once the Team Formation period begins This page will be updated with the Team Formation link once available. More information about and Team Formation can also be found here↗.",
    "how can I get involved?" : "https://www.logicolympiad.org/news-and-events/get-involved",
    "how do I get my certificate for the olympiad?" : "When the Final Round has concluded we will send out certificates to all who qualify.",
    "how is the olympiad structured?" : "The ILO starts off with 3 preliminary rounds which will be taken completely online through our test portal. From the results of the preliminary round finalist will be determined and those finalist will be invited to participate in the final in-person round at Stanford University.",
    "how do I pay for registration?" : "Registration payment can be found in the test portal after you have created an account. Make sure that you have verified your account through the email address provided otherwise payment option will not appear.",
    "can you help with my visa?" : "Finalists from outside of the United States are responsible for securing their own visas for the Final Round. However, we can assist by providing documentation stating your participation in the ILO Final Round. Please reach out via email if this is applies."
}

# Connecting our app to DB using sqlite3
def init_db():
    con = sqlite3.connect('database.db')
    con.row_factory = sqlite3.Row
    return con
def log_to_db(username, message_text, reply_text, isreplied):
    con = init_db()
    con.execute(
        "INSERT INTO chats (ts, username, message, reply, is_replied) VALUES (?,?,?,?,?)",
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
         username,
         message_text,
         reply_text,
         1 if isreplied else 0)
    )
    con.commit()
    con.close()

# Load the data from DB, and calculate simple statistics  for admin
def get_stats():
    con = init_db()
    cur = con.cursor()
    # Total number of messages we got
    cur.execute("SELECT COUNT(*) FROM chats") # counting the number of rows on table 'charts'
    total = cur.fetchone()[0] or 0 # retrive the result of above SQL code
    cur.execute("SELECT COUNT(*) FROM chats WHERE is_replied=1") # number of answered questions
    answered = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM chats WHERE is_replied=0") # number of not answered questions
    no_answered = cur.fetchone()[0] or 0
    con.close()
    return total, answered, no_answered

def log_to_csv(username, message_text, reply_text, isreplied):
    log_file = "chat_log.csv"
    file_exists = os.path.isfile(log_file)
    with open(log_file, mode="a", newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['timestamp', 'username', 'message', 'reply', 'isreplied'])
        writer.writerow(
            [datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             username,
             message_text,
             reply_text,
             isreplied
             ]
        )


@client.event
async def on_ready():
    print(f"Bot is online as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user: # we check whether the user who leave the chat is our chatbot.
        return
    print(f"Message: {message.content}")

    # user_msg ==> What user sent on our discord server
    user_msg = message.content.lower().strip()

    if user_msg == "!exam_start":
        await message.channel.send("on May 25th")
        return

    if user_msg == "!stats":
        total, answered, no_answered = get_stats()
        reply = f"---General Statistics---\n- Total messages : {total}\n- Answered by AI: {answered} \n- Fallback replies: {no_answered}\n"


        await message.channel.send(reply)
        return

    # Requirments.
    # Ensure GPT responses exactly same as we have in faq_data
    # If the question can not answer with faq_data, GPT should
    # reply like 'Thank you for your question! A support team will get back to you soon"
    # --> NO follow-up questions to users

    system_prompt = f"""
        Answer to the user query based on {faq_data}

        You must  follow these rules:
        1. Do NOT ask follow-up questions
        2. If the question cannot be answered based on the answers given, then respond with "Thank you for your question: A support team will get back to you soon"
        3. If the question is a greeting, then respond back with a greeting
        """
    response = client_ai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages = [
            {"role" : "system", "content": system_prompt},
            {"role" : "user", "content": user_msg}
        ]
    )

    reply = response.choices[0].message.content.strip() # Extracting the response of GPT model
    if reply == "Thank you for your question: A support team will get back to you soon":
        isreplied = False
    else:
        isreplied = True
    await message.channel.send(reply)

    log_to_db(str(message.author),message.content, reply, isreplied)

client.run(os.getenv("DISCORD_BOT_TOKEN", ""))