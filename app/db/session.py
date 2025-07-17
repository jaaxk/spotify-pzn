from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from contextlib import contextmanager

# Get database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Create database engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Enable connection liveness checks
    pool_size=5,         # Number of connections to keep open in the pool
    max_overflow=10,     # Max number of connections to create beyond pool_size
    pool_timeout=30,     # Seconds to wait before giving up on getting a connection
    pool_recycle=1800,   # Recycle connections after 30 minutes
    connect_args={
        'connect_timeout': 10,  # Timeout for initial connection
        'keepalives': 1,        # Enable keepalive
        'keepalives_idle': 30,  # Seconds of inactivity before sending keepalive
        'keepalives_interval': 10,  # Seconds between keepalive packets
        'keepalives_count': 5,      # Number of keepalive packets before dropping connection
    }
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db():
    """Get a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# For use with FastAPI's Depends
def get_db_session():
    """For FastAPI dependency injection"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_ctx():
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
