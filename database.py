"""All PostgreSQL reads and writes used by LearnSelf."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


DEFAULT_LESSONS = [
    ("Python foundations", "Variables, collections, and control flow"),
    ("Functions", "Parameters, return values, and scope"),
    ("Working with APIs", "Requests, JSON, and error handling"),
    ("Mini project", "Build and reflect on a small application"),
]


class Base(DeclarativeBase):
    pass


class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(280))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class Chat(Base):
    __tablename__ = "chats"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), default="New learning chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Memory(Base):
    __tablename__ = "learner_memories"
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column("memory_key", String(80))
    value: Mapped[str] = mapped_column("memory_value", Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Database:
    """A small repository: one class, one PostgreSQL connection, clear methods."""

    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self._add_default_lessons()

    def _add_default_lessons(self) -> None:
        with Session(self.engine) as session:
            if session.scalar(select(func.count()).select_from(Lesson)) == 0:
                session.add_all(Lesson(title=title, description=description) for title, description in DEFAULT_LESSONS)
                session.commit()

    # Learning progress -----------------------------------------------------
    def lessons(self) -> list[Lesson]:
        with Session(self.engine) as session:
            return list(session.scalars(select(Lesson).order_by(Lesson.id)))

    def set_lesson_complete(self, lesson_id: int, completed: bool) -> None:
        with Session(self.engine) as session:
            lesson = session.get(Lesson, lesson_id)
            if lesson is None:
                raise ValueError("Lesson not found")
            lesson.completed = completed
            session.commit()

    def progress(self) -> tuple[int, int, int]:
        with Session(self.engine) as session:
            done, total = session.execute(
                select(func.count(Lesson.id).filter(Lesson.completed.is_(True)), func.count(Lesson.id))
            ).one()
        return done, total, round(done / total * 100) if total else 0

    # Conversations ---------------------------------------------------------
    def new_chat(self) -> str:
        chat = Chat(id=str(uuid4()))
        with Session(self.engine) as session:
            session.add(chat)
            session.commit()
        return chat.id

    def chat_exists(self, chat_id: str) -> bool:
        with Session(self.engine) as session:
            return session.get(Chat, chat_id) is not None

    def add_message(self, chat_id: str, role: str, content: str) -> None:
        with Session(self.engine) as session:
            session.add(Message(chat_id=chat_id, role=role, content=content))
            session.commit()

    def messages(self, chat_id: str, limit: int | None = None) -> list[Message]:
        with Session(self.engine) as session:
            query = select(Message).where(Message.chat_id == chat_id).order_by(Message.id.desc())
            if limit:
                query = query.limit(limit)
            return list(reversed(session.scalars(query).all()))

    # Learner memory --------------------------------------------------------
    def memories(self, chat_id: str) -> list[Memory]:
        with Session(self.engine) as session:
            return list(session.scalars(select(Memory).where(Memory.chat_id == chat_id)))

    def save_memory(self, chat_id: str, key: str, value: str) -> None:
        with Session(self.engine) as session:
            memory = session.scalar(select(Memory).where(Memory.chat_id == chat_id, Memory.key == key))
            if memory:
                memory.value = value
            else:
                session.add(Memory(chat_id=chat_id, key=key, value=value))
            session.commit()
