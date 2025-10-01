from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL

if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable is not set. Please set it in your .env file.")

# Create engine
engine = create_engine(DATABASE_URL, echo=True)  # Set echo=False in production

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base for models
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)