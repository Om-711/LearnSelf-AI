"""All PostgreSQL reads and writes used by LearnSelf."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="Not Started")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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

    # Subjects and topics --------------------------------------------------
    def subjects(self) -> list[Subject]:
        with Session(self.engine) as session:
            return list(session.scalars(select(Subject).order_by(Subject.name)).all())

    def add_subject(self, name: str) -> None:
        with Session(self.engine) as session:
            if session.scalar(select(Subject).where(Subject.name == name)) is None:
                session.add(Subject(name=name))
                session.commit()

    def delete_subject(self, subject_id: int) -> None:
        with Session(self.engine) as session:
            session.execute(delete(Topic).where(Topic.subject_id == subject_id))
            session.execute(delete(Subject).where(Subject.id == subject_id))
            session.commit()

    def topics(self, subject_id: int) -> list[Topic]:
        with Session(self.engine) as session:
            return list(session.scalars(
                select(Topic).where(Topic.subject_id == subject_id).order_by(Topic.id)
            ).all())

    def add_topic(self, subject_id: int, name: str) -> None:
        with Session(self.engine) as session:
            session.add(Topic(subject_id=subject_id, name=name))
            session.commit()

    def delete_topic(self, topic_id: int) -> None:
        with Session(self.engine) as session:
            session.execute(delete(Topic).where(Topic.id == topic_id))
            session.commit()

    def set_topic_status(self, topic_id: int, status: str) -> None:
        if status not in {"Not Started", "In Progress", "Completed"}:
            raise ValueError("Invalid topic status")
        with Session(self.engine) as session:
            topic = session.get(Topic, topic_id)
            if topic is None:
                raise ValueError("Topic not found")
            topic.status = status
            session.commit()

    def topic_progress(self) -> tuple[int, int, int]:
        with Session(self.engine) as session:
            completed, total = session.execute(
                select(
                    func.count(Topic.id).filter(Topic.status == "Completed"),
                    func.count(Topic.id),
                )
            ).one()
        return completed, total, round(completed / total * 100) if total else 0

    # Conversations ---------------------------------------------------------
    def new_chat(self) -> str:
        chat_id = str(uuid4())
        with Session(self.engine) as session:
            session.add(Chat(id=chat_id))
            session.commit()
        return chat_id

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
