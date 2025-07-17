import logging
import time
from typing import Optional, Tuple
from sqlalchemy.exc import OperationalError
from .db import init_db, QdrantVectorStore

logger = logging.getLogger(__name__)

def wait_for_db(max_retries: int = 5, delay: float = 2.0) -> bool:
    """Wait for database to become available"""
    from .db.session import engine
    
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute("SELECT 1")
                logger.info("Database connection successful")
                return True
        except OperationalError as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to connect to database after {max_retries} attempts")
                raise
            logger.warning(f"Database connection attempt {attempt + 1} failed, retrying in {delay} seconds...")
            time.sleep(delay)
    return False

def init() -> None:
    """Initialize the database and create tables"""
    logger.info("Starting database initialization...")
    
    # Wait for database to be ready
    wait_for_db()
    
    # Initialize SQLAlchemy models and create tables
    try:
        logger.info("Initializing database tables...")
        init_db()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise
    
    # Initialize Qdrant collection with retry
    for attempt in range(3):
        try:
            logger.info("Initializing Qdrant vector store...")
            vector_store = QdrantVectorStore()
            logger.info("Successfully connected to Qdrant vector store")
            break
        except Exception as e:
            if attempt == 2:  # Last attempt
                logger.error("Failed to initialize Qdrant vector store after multiple attempts")
                raise
            logger.warning(f"Qdrant initialization attempt {attempt + 1} failed, retrying...")
            time.sleep(2 ** attempt)  # Exponential backoff
    
    logger.info("Database initialization complete")

def main() -> None:
    """For manual initialization"""
    import logging
    logging.basicConfig(level=logging.INFO)
    init()

if __name__ == "__main__":
    main()
