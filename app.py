from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

from database import Database
from memory_workflow import build_remember_graph
from tutor import answer_stream

load_dotenv()
st.set_page_config(page_title="LearnSelf | Study companion", page_icon="📚", layout="wide")


def setting(name: str) -> str | None:
    """Read a setting from local environment variables or Streamlit secrets."""
    value = os.getenv(name)
    if value:
        return value.strip()

    try:
        value = st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        value = None

    return str(value).strip() if value else None


@st.cache_resource
def get_database(database_url: str, cache_version: str = "subjects-topics-v2") -> Database:
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
    database_url = setting("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured in the local environment or Streamlit secrets.")
    db = get_database(database_url)
except Exception as error:
    st.error(f"Database connection failed: {error}")
    st.info("For local use, configure `.env`. For Streamlit Cloud, add DATABASE_URL under App settings → Secrets.")
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

topic_completed, topic_total, topic_percent = db.topic_progress()
metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Overall completion", f"{topic_percent}%")
metric_b.metric("Topics completed", f"{topic_completed}/{topic_total}")
metric_c.metric("Saved memories", len(db.memories(st.session_state.chat_id)))
st.progress(topic_percent / 100)

st.subheader("Study plan")
subject_form, topic_form = st.columns(2)
with subject_form:
    with st.form("add-subject", clear_on_submit=True):
        st.markdown("**Add a subject**")
        subject_name = st.text_input("Subject name", placeholder="e.g. Mathematics")
        if st.form_submit_button("Add subject", type="primary"):
            if subject_name.strip():
                db.add_subject(subject_name.strip())
                st.rerun()
            st.warning("Enter a subject name first.")

subjects = db.subjects()
with topic_form:
    with st.form("add-topic", clear_on_submit=True):
        st.markdown("**Add a topic**")
        if subjects:
            subject_options = {subject.name: subject.id for subject in subjects}
            selected_subject = st.selectbox("Subject", list(subject_options))
            topic_name = st.text_input("Topic name", placeholder="e.g. Quadratic equations")
            if st.form_submit_button("Add topic"):
                if topic_name.strip():
                    db.add_topic(subject_options[selected_subject], topic_name.strip())
                    st.rerun()
                st.warning("Enter a topic name first.")
        else:
            st.info("Add a subject before adding topics.")

if subjects:
    st.markdown("**Topics**")
    for subject in subjects:
        with st.expander(subject.name, expanded=True):
            if st.button("Remove subject", key=f"delete-subject-{subject.id}", type="secondary"):
                db.delete_subject(subject.id)
                st.rerun()
            topics = db.topics(subject.id)
            if not topics:
                st.caption("No topics yet.")
            for topic in topics:
                status_column, remove_column = st.columns([5, 1])
                with status_column:
                    status = st.selectbox(
                        topic.name,
                        ["Not Started", "In Progress", "Completed"],
                        index=["Not Started", "In Progress", "Completed"].index(topic.status),
                        key=f"topic-status-{topic.id}",
                    )
                with remove_column:
                    st.write("")
                    remove_topic = st.button("Remove", key=f"delete-topic-{topic.id}")
                if remove_topic:
                    db.delete_topic(topic.id)
                    st.rerun()
                if status != topic.status:
                    db.set_topic_status(topic.id, status)
                    st.rerun()
else:
    st.info("Create your first subject to start tracking topics.")

st.divider()
st.subheader("AI learning assistant")
st.caption("Enter any topic and get a simple explanation, key concepts, an example, and practice questions.")
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
    saved_topics = [topic for subject in subjects for topic in db.topics(subject.id)]
    suggestion = f"Explain {saved_topics[0].name}" if saved_topics else "Explain recursion in Python"
    st.info(f'Try: "{suggestion}"')
for message in conversation:
    with st.chat_message(message.role):
        st.markdown(message.content)

question = st.chat_input('Enter a topic, for example: "Explain recursion in Python"')
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
                stream_with_loading(answer_stream(question, f"{topic_completed}/{topic_total} topics complete", history, memories))
            )
            db.add_message(chat_id, "assistant", reply)
            build_remember_graph(db).invoke({"chat_id": chat_id, "user_message": question, "memories": []})
        except Exception as error:
            error_text = str(error)
            if "401" in error_text or "UNAUTHENTICATED" in error_text:
                st.error(
                    "Gemini authentication failed. Update GEMINI_API_KEY in "
                    "learnself-ai-task/.env with a valid Google AI Studio API key, "
                    "then restart Streamlit. Do not use an OAuth access token."
                )
            elif "403" in error_text or "PERMISSION_DENIED" in error_text:
                st.error(
                    "Gemini access is denied for this API key's Google project. "
                    "Create or select an approved Google AI Studio project, generate "
                    "a new API key for it, update .env, and restart Streamlit."
                )
            else:
                st.error(f"I couldn't answer right now: {error}")

st.caption("Conversation and chat-specific learner memory are stored in PostgreSQL.")
