from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from database import Database
from memory_workflow import build_remember_graph
from tutor import answer_stream

load_dotenv()
st.set_page_config(page_title="LearnSelf | Study companion", page_icon="📚", layout="wide")


@st.cache_resource
def get_database() -> Database:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing. Copy .env.example to .env and configure PostgreSQL.")
    return Database(database_url)


def stream_with_loading(chunks):
    """Show feedback during Gemini's first-token delay, then yield the live answer."""
    loading = st.empty()
    loading.info("Gemini is preparing your answer…")
    started = False
    try:
        for chunk in chunks:
            if not started:
                loading.empty()
                started = True
            yield chunk
    finally:
        loading.empty()


st.markdown("""
<style>
    .block-container { max-width: 1000px; padding-top: 2rem; }
    .chat-id { color: #64748b; font-size: 0.82rem; font-family: monospace; }
</style>
""", unsafe_allow_html=True)
try:
    db = get_database()
except Exception as error:
    st.error(f"Database connection failed: {error}")
    st.info("Run `docker compose up -d`, copy `.env.example` to `.env`, then restart the app.")
    st.stop()

if "chat_id" not in st.session_state or not db.chat_exists(st.session_state.chat_id):
    st.session_state.chat_id = db.new_chat()

title, action = st.columns([4, 1])
with title:
    st.title("LearnSelf")
    st.caption("Your personal study companion — track progress, ask questions, and build momentum.")
with action:
    st.write("")
    if st.button("＋ New chat", type="primary", use_container_width=True):
        st.session_state.chat_id = db.new_chat()
        st.rerun()

completed, total, percent = db.progress()
metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Course progress", f"{percent}%")
metric_b.metric("Lessons done", f"{completed}/{total}")
metric_c.metric("Saved memories", len(db.memories(st.session_state.chat_id)))
st.progress(percent / 100)

with st.expander("Update lesson progress", expanded=False):
    for lesson in db.lessons():
        checked = st.checkbox(lesson.title, value=lesson.completed, key=f"lesson-{lesson.id}", help=lesson.description)
        if checked != lesson.completed:
            db.set_lesson_complete(lesson.id, checked)
            st.rerun()

st.divider()
st.subheader("Learning assistant")
st.markdown(f"<div class='chat-id'>Chat ID: {st.session_state.chat_id}</div>", unsafe_allow_html=True)

with st.expander("What I remember about this chat", expanded=False):
    memories = db.memories(st.session_state.chat_id)
    if memories:
        for memory in memories:
            st.write(f"**{memory.key.replace('_', ' ').title()}:** {memory.value}")
    else:
        st.caption("I will remember learning preferences or goals that you explicitly share in this chat.")

conversation = db.messages(st.session_state.chat_id)
if not conversation:
    st.info("Try: “I am new to Python. Explain functions using simple real-world examples.”")
for message in conversation:
    with st.chat_message(message.role):
        st.markdown(message.content)

question = st.chat_input("Ask for an explanation, quiz, study plan, or example")
if question:
    chat_id = st.session_state.chat_id
    db.add_message(chat_id, "user", question)
    with st.chat_message("user"):
        st.markdown(question)

    history = "\n".join(f"{item.role}: {item.content}" for item in db.messages(chat_id, limit=10)[:-1])
    memories = "\n".join(f"{item.key}: {item.value}" for item in db.memories(chat_id))
    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(
                stream_with_loading(answer_stream(question, f"{completed}/{total} lessons complete", history, memories))
            )
            db.add_message(chat_id, "assistant", reply)
            build_remember_graph(db).invoke({"chat_id": chat_id, "user_message": question, "memories": []})
        except Exception as error:
            st.error(f"I couldn't answer right now: {error}")

st.caption("Conversation and chat-specific learner memory are stored in PostgreSQL.")
