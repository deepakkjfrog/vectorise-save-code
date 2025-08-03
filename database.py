from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import VECTOR
from config import Config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database engine
engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Repository(Base):
    __tablename__ = "repositories"
    
    id = Column(Integer, primary_key=True, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    repo_url = Column(String(500), nullable=False)
    clone_path = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status = Column(String(50), default='pending')
    
    # Relationships
    code_files = relationship("CodeFile", back_populates="repository", cascade="all, delete-orphan")

class CodeFile(Base):
    __tablename__ = "code_files"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_extension = Column(String(50))
    file_size = Column(Integer)
    content_hash = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    repository = relationship("Repository", back_populates="code_files")
    code_chunks = relationship("CodeChunk", back_populates="code_file", cascade="all, delete-orphan")

class CodeChunk(Base):
    __tablename__ = "code_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("code_files.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    token_count = Column(Integer)
    embedding = Column(VECTOR(1536))  # OpenAI embedding dimension
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    code_file = relationship("CodeFile", back_populates="code_chunks")

# Create indexes
Index('idx_code_chunks_embedding', CodeChunk.embedding, postgresql_using='ivfflat', postgresql_with={'lists': 100})

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def test_connection():
    """Test database connection"""
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False 