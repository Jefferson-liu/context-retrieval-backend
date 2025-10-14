from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL

if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable is not set. Please set it in your .env file.")

# Create engine
engine = create_async_engine(DATABASE_URL, echo=True)  # Set echo=False in production

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

# Base for models
Base = declarative_base()

# Ensure all model modules register with Base metadata
from infrastructure.database import models as _models  # noqa: E402,F401

async def get_db():
    db = SessionLocal()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
async def drop_tables():
    async with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table.name} CASCADE"))