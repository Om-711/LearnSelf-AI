# LearnSelf

LearnSelf is a personal learning companion for tracking course progress and getting contextual help from an AI tutor. It combines a simple learning dashboard with a Gemini-powered chat experience that remembers the learner's stated goals and preferred learning style within each conversation.

## Highlights

- Track completed lessons and view overall course progress.
- Persist learning progress, conversations, and memory in PostgreSQL.
- Ask Gemini for explanations, examples, quizzes, and study plans.
- Stream answers live, with feedback while the model is preparing its first response.
- Create independent conversations with visible chat IDs.
- Preserve the complete message history for each chat.
- Save explicit learning preferences, goals, skill level, and difficult topics through a LangGraph `remember` node.
- Personalize future responses using recent history, current progress, and saved chat memory.

## Tech stack

Python, Streamlit, PostgreSQL, SQLAlchemy, LangGraph, Google Gemini API, Docker Compose, and python-dotenv.

## Getting started

### Prerequisites

- Python 3.10 or later
- Docker Desktop
- A Gemini API key

### Run locally

```powershell
git clone 
cd learnself-ai-task
Copy-Item .env.example .env
docker compose up -d
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`.



### Environment variables

```env
DATABASE_URL=postgresql+psycopg://learnself:learnself@localhost:5432/learnself
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

`docker compose up -d` starts the local PostgreSQL database. The application creates its tables and seeds the initial lessons automatically.

## How memory works

Every chat has a unique ID. When a learner sends a message, Gemini receives the learner's progress, recent messages, and the saved memory for that chat. Once the answer finishes streaming, the LangGraph `remember` node extracts only stable details that the learner explicitly provided, such as:

- "I am new to Python" -> skill level
- "Use real-world examples" -> explanation preference
- "I want to prepare for an API interview" -> learning goal

These memories are stored in PostgreSQL and shown in the **What I remember about this chat** section. They are used only in that specific chat.

## Project structure

```text
app.py                Streamlit interface
database.py           PostgreSQL models and all data operations
tutor.py              Gemini streaming adapter
memory_workflow.py    LangGraph memory extraction workflow
docker-compose.yml    Local PostgreSQL service
```

## Design notes

The Streamlit UI keeps the learning loop small: view progress, mark lessons complete, and ask for help. PostgreSQL stores progress and chat data, while Gemini is called on the server so the API key is not exposed in the browser. The memory workflow is separate from response generation: Gemini streams the answer first, then the LangGraph `remember` node extracts only facts the learner explicitly shared.

The main risks are temporary Gemini failures, inaccurate AI explanations, and storing learner information without enough control. The app reports API errors clearly, asks Gemini to be transparent when uncertain, and limits memory to explicit learning details scoped to one chat. A production version should add authentication, memory edit/delete controls, retries, rate limits, approved course-content retrieval, database migrations, automated tests, and monitoring.

## Roadmap

- Add authentication and per-user courses.
- Let learners edit or delete saved memories.
- Ground Gemini responses in approved course material.
- Add quizzes, mastery signals, and next-lesson recommendations.
- Add migrations, automated tests, rate limits, and observability for production use.
