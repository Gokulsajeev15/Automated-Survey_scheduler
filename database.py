from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    email = Column(String(100), unique=True)
    age = Column(Integer)
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.now)
    scheduled_at = Column(DateTime)

# Database engine and session setup
engine = create_engine('sqlite:///user_data.db', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)