#!/usr/bin/env python3

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
import uvicorn
import asyncio
import logging
from datetime import datetime
import os
import hashlib
from sqlalchemy import create_engine, text, MetaData
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import threading
import time

# Import our existing modules
from config import Config
from git_manager import GitManager
from file_processor import FileProcessor
from embedding_service import EmbeddingService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Code Vectorizer API",
    description="API for vectorizing codebases and storing in PostgreSQL with pgvector",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class VectorizeRequest(BaseModel):
    repo_url: HttpUrl
    repo_name: Optional[str] = None
    github_token: Optional[str] = None
    github_username: Optional[str] = None
    username: str  # User identifier
    chunk_size: Optional[int] = 1000
    chunk_overlap: Optional[int] = 200
    max_file_size: Optional[int] = 1048576

class VectorizeResponse(BaseModel):
    job_id: str
    status: str
    message: str
    created_at: datetime

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    error: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    username: str
    repo_name: Optional[str] = None
    limit: Optional[int] = 10
    similarity_threshold: Optional[float] = 0.7

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total: int
    query: str

class UserReposResponse(BaseModel):
    username: str
    repositories: List[Dict[str, Any]]

# Global state for job tracking
jobs = {}
job_lock = threading.Lock()

class DatabaseManager:
    def __init__(self):
        self.base_url = Config.DATABASE_URL
        self.engines = {}
        self.sessions = {}
        self.lock = threading.Lock()
    
    def get_user_schema_name(self, username: str, repo_name: str) -> str:
        """Generate schema name for user and repository"""
        # Create a safe schema name
        safe_username = "".join(c for c in username if c.isalnum() or c in '_').lower()
        safe_repo = "".join(c for c in repo_name if c.isalnum() or c in '_').lower()
        schema_name = f"user_{safe_username}_repo_{safe_repo}"
        
        # Limit length to avoid PostgreSQL limits
        if len(schema_name) > 50:
            schema_name = schema_name[:50]
        
        return schema_name
    
    def get_engine(self, schema_name: str):
        """Get or create database engine for schema"""
        with self.lock:
            if schema_name not in self.engines:
                # Create engine with schema-specific connection
                engine = create_engine(self.base_url, echo=False)
                self.engines[schema_name] = engine
            return self.engines[schema_name]
    
    def create_schema(self, schema_name: str):
        """Create schema and tables for a user repository"""
        engine = self.get_engine(schema_name)
        
        with engine.connect() as conn:
            # Create schema
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            
            # Create tables in the schema
            tables_sql = f"""
            -- Enable pgvector extension in the schema
            CREATE EXTENSION IF NOT EXISTS vector;
            
            -- Create repositories table
            CREATE TABLE IF NOT EXISTS {schema_name}.repositories (
                id SERIAL PRIMARY KEY,
                repo_name VARCHAR(255) NOT NULL UNIQUE,
                repo_url VARCHAR(500) NOT NULL,
                clone_path VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(50) DEFAULT 'pending'
            );
            
            -- Create code_files table
            CREATE TABLE IF NOT EXISTS {schema_name}.code_files (
                id SERIAL PRIMARY KEY,
                repository_id INTEGER REFERENCES {schema_name}.repositories(id) ON DELETE CASCADE,
                file_path VARCHAR(500) NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                file_extension VARCHAR(50),
                file_size INTEGER,
                content_hash VARCHAR(64),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(repository_id, file_path)
            );
            
            -- Create code_chunks table
            CREATE TABLE IF NOT EXISTS {schema_name}.code_chunks (
                id SERIAL PRIMARY KEY,
                file_id INTEGER REFERENCES {schema_name}.code_files(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                token_count INTEGER,
                embedding vector(1536),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_{schema_name}_repositories_repo_name 
            ON {schema_name}.repositories(repo_name);
            
            CREATE INDEX IF NOT EXISTS idx_{schema_name}_code_files_repository_id 
            ON {schema_name}.code_files(repository_id);
            
            CREATE INDEX IF NOT EXISTS idx_{schema_name}_code_files_file_path 
            ON {schema_name}.code_files(file_path);
            
            CREATE INDEX IF NOT EXISTS idx_{schema_name}_code_chunks_file_id 
            ON {schema_name}.code_chunks(file_id);
            
            CREATE INDEX IF NOT EXISTS idx_{schema_name}_code_chunks_embedding 
            ON {schema_name}.code_chunks USING ivfflat (embedding vector_cosine_ops);
            """
            
            # Execute each statement separately
            for statement in tables_sql.split(';'):
                if statement.strip():
                    conn.execute(text(statement))
            
            conn.commit()
    
    @contextmanager
    def get_session(self, schema_name: str):
        """Get database session for a schema"""
        engine = self.get_engine(schema_name)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

# Global database manager
db_manager = DatabaseManager()

class JobManager:
    def __init__(self):
        self.jobs = {}
        self.lock = threading.Lock()
    
    def create_job(self, job_id: str, username: str, repo_name: str, repo_url: str):
        """Create a new job"""
        with self.lock:
            self.jobs[job_id] = {
                'job_id': job_id,
                'username': username,
                'repo_name': repo_name,
                'repo_url': str(repo_url),
                'status': 'pending',
                'progress': {
                    'step': 'initializing',
                    'files_discovered': 0,
                    'files_processed': 0,
                    'chunks_created': 0,
                    'chunks_with_embeddings': 0,
                    'chunks_saved': 0
                },
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'error': None
            }
    
    def update_job(self, job_id: str, status: str, progress: Dict = None, error: str = None):
        """Update job status and progress"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = status
                self.jobs[job_id]['updated_at'] = datetime.now()
                if progress:
                    self.jobs[job_id]['progress'].update(progress)
                if error:
                    self.jobs[job_id]['error'] = error
    
    def get_job(self, job_id: str):
        """Get job by ID"""
        with self.lock:
            return self.jobs.get(job_id)

# Global job manager
job_manager = JobManager()

def generate_job_id(username: str, repo_name: str) -> str:
    """Generate unique job ID"""
    timestamp = str(int(time.time()))
    hash_input = f"{username}_{repo_name}_{timestamp}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:12]

async def vectorize_repository_async(
    job_id: str,
    username: str,
    repo_url: str,
    repo_name: str,
    github_token: Optional[str] = None,
    github_username: Optional[str] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    max_file_size: int = 1048576
):
    """Async function to vectorize repository"""
    try:
        # Update job status
        job_manager.update_job(job_id, 'processing', {'step': 'cloning_repository'})
        
        # Generate schema name
        schema_name = db_manager.get_user_schema_name(username, repo_name)
        
        # Create schema and tables
        db_manager.create_schema(schema_name)
        
        # Initialize components
        git_manager = GitManager(github_token, github_username)
        file_processor = FileProcessor()
        embedding_service = EmbeddingService()
        
        # Override config for this job
        file_processor.chunk_size = chunk_size
        file_processor.chunk_overlap = chunk_overlap
        file_processor.max_file_size = max_file_size
        
        # Step 1: Clone repository
        job_manager.update_job(job_id, 'processing', {'step': 'cloning_repository'})
        clone_path = git_manager.clone_repository(repo_url, repo_name)
        
        # Step 2: Save repository to database
        job_manager.update_job(job_id, 'processing', {'step': 'saving_repository'})
        with db_manager.get_session(schema_name) as db:
            # Check if repository already exists
            existing_repo = db.execute(text(f"""
                SELECT id FROM {schema_name}.repositories 
                WHERE repo_name = :repo_name
            """), {
                'repo_name': repo_name
            }).fetchone()
            
            if existing_repo:
                # Update existing repository
                db.execute(text(f"""
                    UPDATE {schema_name}.repositories 
                    SET repo_url = :repo_url, clone_path = :clone_path, status = 'processing', updated_at = CURRENT_TIMESTAMP
                    WHERE repo_name = :repo_name
                """), {
                    'repo_name': repo_name,
                    'repo_url': str(repo_url),
                    'clone_path': clone_path
                })
                repository_id = existing_repo[0]
            else:
                # Insert new repository
                result = db.execute(text(f"""
                    INSERT INTO {schema_name}.repositories (repo_name, repo_url, clone_path, status)
                    VALUES (:repo_name, :repo_url, :clone_path, 'processing')
                    RETURNING id
                """), {
                    'repo_name': repo_name,
                    'repo_url': str(repo_url),
                    'clone_path': clone_path
                })
                repository_id = result.fetchone()[0]
            
            db.commit()
        
        # Step 3: Discover code files
        job_manager.update_job(job_id, 'processing', {'step': 'discovering_files'})
        code_files = file_processor.discover_code_files(clone_path)
        job_manager.update_job(job_id, 'processing', {
            'step': 'processing_files',
            'files_discovered': len(code_files)
        })
        
        if not code_files:
            job_manager.update_job(job_id, 'completed', {
                'step': 'completed',
                'files_discovered': 0,
                'files_processed': 0,
                'chunks_created': 0,
                'chunks_with_embeddings': 0,
                'chunks_saved': 0
            })
            return
        
        # Step 4: Process files and create chunks
        all_chunks = []
        processed_files = []
        
        for i, file_info in enumerate(code_files):
            job_manager.update_job(job_id, 'processing', {
                'step': 'processing_files',
                'files_discovered': len(code_files),
                'files_processed': i,
                'current_file': file_info['file_name']
            })
            
            chunks = file_processor.process_file(file_info['absolute_path'])
            if chunks:
                for chunk in chunks:
                    chunk['file_info'] = file_info
                all_chunks.extend(chunks)
                processed_files.append(file_info)
        
        job_manager.update_job(job_id, 'processing', {
            'step': 'saving_files',
            'files_discovered': len(code_files),
            'files_processed': len(processed_files),
            'chunks_created': len(all_chunks)
        })
        
        # Step 5: Save files to database and track changes
        with db_manager.get_session(schema_name) as db:
            file_mapping = {}
            files_to_update = []
            files_to_insert = []
            
            for file_info in processed_files:
                content_hash = git_manager.get_file_content_hash(file_info['absolute_path'])
                
                # Check if file exists and if content has changed
                existing_file = db.execute(text(f"""
                    SELECT id, content_hash FROM {schema_name}.code_files 
                    WHERE repository_id = :repository_id AND file_path = :file_path
                """), {
                    'repository_id': repository_id,
                    'file_path': file_info['file_path']
                }).fetchone()
                
                if existing_file:
                    existing_file_id, existing_hash = existing_file
                    if existing_hash != content_hash:
                        # File content has changed, mark for update
                        files_to_update.append((existing_file_id, file_info, content_hash))
                    file_mapping[file_info['file_path']] = existing_file_id
                else:
                    # New file, mark for insertion
                    files_to_insert.append((file_info, content_hash))
            
            # Insert new files
            for file_info, content_hash in files_to_insert:
                result = db.execute(text(f"""
                    INSERT INTO {schema_name}.code_files 
                    (repository_id, file_path, file_name, file_extension, file_size, content_hash)
                    VALUES (:repository_id, :file_path, :file_name, :file_extension, :file_size, :content_hash)
                    RETURNING id
                """), {
                    'repository_id': repository_id,
                    'file_path': file_info['file_path'],
                    'file_name': file_info['file_name'],
                    'file_extension': file_info['file_extension'],
                    'file_size': file_info['file_size'],
                    'content_hash': content_hash
                })
                file_id = result.fetchone()[0]
                file_mapping[file_info['file_path']] = file_id
            
            # Update changed files
            for file_id, file_info, content_hash in files_to_update:
                db.execute(text(f"""
                    UPDATE {schema_name}.code_files 
                    SET file_size = :file_size, content_hash = :content_hash
                    WHERE id = :file_id
                """), {
                    'file_id': file_id,
                    'file_size': file_info['file_size'],
                    'content_hash': content_hash
                })
                
                # Delete existing chunks for this file since content changed
                db.execute(text(f"""
                    DELETE FROM {schema_name}.code_chunks 
                    WHERE file_id = :file_id
                """), {
                    'file_id': file_id
                })
            
            db.commit()
        
        # Step 6: Generate embeddings
        job_manager.update_job(job_id, 'processing', {
            'step': 'generating_embeddings',
            'files_discovered': len(code_files),
            'files_processed': len(processed_files),
            'chunks_created': len(all_chunks)
        })
        
        processed_chunks = embedding_service.process_chunks(all_chunks)
        
        job_manager.update_job(job_id, 'processing', {
            'step': 'saving_chunks',
            'files_discovered': len(code_files),
            'files_processed': len(processed_files),
            'chunks_created': len(all_chunks),
            'chunks_with_embeddings': len(processed_chunks),
            'files_to_insert': len(files_to_insert),
            'files_to_update': len(files_to_update)
        })
        
        # Step 7: Save chunks and embeddings
        with db_manager.get_session(schema_name) as db:
            saved_count = 0
            
            # Only process chunks for files that were inserted or updated
            files_that_changed = set()
            for file_info, _ in files_to_insert:
                files_that_changed.add(file_info['file_path'])
            for _, file_info, _ in files_to_update:
                files_that_changed.add(file_info['file_path'])
            
            for chunk in processed_chunks:
                file_path = chunk['file_info']['file_path']
                file_id = file_mapping.get(file_path)
                
                # Only save chunks for files that changed or are new
                if file_id is None or file_path not in files_that_changed:
                    continue
                
                db.execute(text(f"""
                    INSERT INTO {schema_name}.code_chunks 
                    (file_id, chunk_index, content, start_line, end_line, token_count, embedding)
                    VALUES (:file_id, :chunk_index, :content, :start_line, :end_line, :token_count, :embedding)
                """), {
                    'file_id': file_id,
                    'chunk_index': chunk.get('chunk_index', 0),
                    'content': chunk['content'],
                    'start_line': chunk['start_line'],
                    'end_line': chunk['end_line'],
                    'token_count': chunk['token_count'],
                    'embedding': chunk['embedding']
                })
                saved_count += 1
            
            db.commit()
        
        # Step 8: Clean up files that no longer exist in the repository
        with db_manager.get_session(schema_name) as db:
            # Get all current file paths in the repository
            current_file_paths = {file_info['file_path'] for file_info in processed_files}
            
            # Find files in database that no longer exist
            db_files = db.execute(text(f"""
                SELECT id, file_path FROM {schema_name}.code_files 
                WHERE repository_id = :repository_id
            """), {
                'repository_id': repository_id
            }).fetchall()
            
            files_to_delete = []
            for db_file_id, db_file_path in db_files:
                if db_file_path not in current_file_paths:
                    files_to_delete.append(db_file_id)
            
            # Delete chunks and files that no longer exist
            if files_to_delete:
                file_ids_str = ','.join(map(str, files_to_delete))
                db.execute(text(f"""
                    DELETE FROM {schema_name}.code_chunks 
                    WHERE file_id IN ({file_ids_str})
                """))
                db.execute(text(f"""
                    DELETE FROM {schema_name}.code_files 
                    WHERE id IN ({file_ids_str})
                """))
            
            db.commit()
        
        # Step 9: Update repository status
        with db_manager.get_session(schema_name) as db:
            db.execute(text(f"""
                UPDATE {schema_name}.repositories 
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE repo_name = :repo_name
            """), {'repo_name': repo_name})
            db.commit()
        
        # Step 10: Cleanup
        git_manager.cleanup_repository(clone_path)
        
        # Update final job status
        job_manager.update_job(job_id, 'completed', {
            'step': 'completed',
            'files_discovered': len(code_files),
            'files_processed': len(processed_files),
            'chunks_created': len(all_chunks),
            'chunks_with_embeddings': len(processed_chunks),
            'chunks_saved': saved_count
        })
        
    except Exception as e:
        logger.error(f"Error in vectorization job {job_id}: {e}")
        job_manager.update_job(job_id, 'failed', error=str(e))
        
        # Update repository status to failed
        try:
            schema_name = db_manager.get_user_schema_name(username, repo_name)
            with db_manager.get_session(schema_name) as db:
                db.execute(text(f"""
                    UPDATE {schema_name}.repositories 
                    SET status = 'failed', updated_at = CURRENT_TIMESTAMP
                    WHERE repo_name = :repo_name
                """), {'repo_name': repo_name})
                db.commit()
        except:
            pass

@app.post("/api/vectorize", response_model=VectorizeResponse)
async def vectorize_code(request: VectorizeRequest, background_tasks: BackgroundTasks):
    """Vectorize a code repository"""
    try:
        # Generate job ID
        repo_name = request.repo_name or str(request.repo_url).split('/')[-1].replace('.git', '')
        job_id = generate_job_id(request.username, repo_name)
        
        # Create job
        job_manager.create_job(job_id, request.username, repo_name, request.repo_url)
        
        # Start background task
        background_tasks.add_task(
            vectorize_repository_async,
            job_id=job_id,
            username=request.username,
            repo_url=str(request.repo_url),
            repo_name=repo_name,
            github_token=request.github_token,
            github_username=request.github_username,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            max_file_size=request.max_file_size
        )
        
        return VectorizeResponse(
            job_id=job_id,
            status="pending",
            message="Vectorization job started",
            created_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error starting vectorization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get job status and progress"""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(**job)

@app.post("/api/search", response_model=SearchResponse)
async def search_code(request: SearchRequest):
    """Search for code using semantic similarity"""
    try:
        # Get query embedding
        embedding_service = EmbeddingService()
        query_embedding = embedding_service.get_embedding(request.query)
        
        if not query_embedding:
            raise HTTPException(status_code=500, detail="Failed to generate query embedding")
        
        # Search in user's repositories
        results = []
        total = 0
        
        # Get user's repositories
        user_repos = get_user_repositories(request.username)
        
        for repo in user_repos:
            if request.repo_name and repo['repo_name'] != request.repo_name:
                continue
            
            schema_name = db_manager.get_user_schema_name(request.username, repo['repo_name'])
            
            try:
                with db_manager.get_session(schema_name) as db:
                    # Search query with direct parameter substitution
                    embedding_str = ','.join(map(str, query_embedding))
                    search_query = f"""
                    SELECT 
                        cc.content,
                        cc.start_line,
                        cc.end_line,
                        cc.token_count,
                        cf.file_path,
                        cf.file_name,
                        r.repo_name,
                        1 - (cc.embedding <=> '[{embedding_str}]'::vector) as similarity
                    FROM {schema_name}.code_chunks cc
                    JOIN {schema_name}.code_files cf ON cc.file_id = cf.id
                    JOIN {schema_name}.repositories r ON cf.repository_id = r.id
                    WHERE 1 - (cc.embedding <=> '[{embedding_str}]'::vector) > {request.similarity_threshold}
                    ORDER BY similarity DESC
                    LIMIT {request.limit}
                    """
                    
                    db_results = db.execute(text(search_query)).fetchall()
                    
                    for row in db_results:
                        results.append({
                            'content': row[0],
                            'start_line': row[1],
                            'end_line': row[2],
                            'token_count': row[3],
                            'file_path': row[4],
                            'file_name': row[5],
                            'repo_name': row[6],
                            'similarity': float(row[7])
                        })
                        total += 1
                        
            except Exception as e:
                logger.error(f"Error searching in schema {schema_name}: {e}")
                continue
        
        # Sort by similarity and limit results
        results.sort(key=lambda x: x['similarity'], reverse=True)
        results = results[:request.limit]
        
        return SearchResponse(
            results=results,
            total=total,
            query=request.query
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/{username}/repos", response_model=UserReposResponse)
async def get_user_repositories(username: str):
    """Get all repositories for a user"""
    try:
        repos = get_user_repositories(username)
        return UserReposResponse(username=username, repositories=repos)
    except Exception as e:
        logger.error(f"Error getting user repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_user_repositories(username: str) -> List[Dict[str, Any]]:
    """Helper function to get user repositories"""
    repos = []
    
    # Get base engine to query for schemas
    base_engine = create_engine(Config.DATABASE_URL)
    
    with base_engine.connect() as conn:
        # Find all schemas for this user
        schemas = conn.execute(text(f"""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name LIKE 'user_{username.lower()}%'
        """)).fetchall()
        
        for schema_row in schemas:
            schema_name = schema_row[0]
            
            try:
                # Get repositories from this schema
                repo_results = conn.execute(text(f"""
                    SELECT repo_name, repo_url, status, created_at, updated_at
                    FROM {schema_name}.repositories
                """)).fetchall()
                
                for repo_row in repo_results:
                    # Get file and chunk counts
                    file_count = conn.execute(text(f"""
                        SELECT COUNT(*) FROM {schema_name}.code_files 
                        WHERE repository_id = (SELECT id FROM {schema_name}.repositories WHERE repo_name = :repo_name)
                    """), {'repo_name': repo_row[0]}).fetchone()[0]
                    
                    chunk_count = conn.execute(text(f"""
                        SELECT COUNT(*) FROM {schema_name}.code_chunks cc
                        JOIN {schema_name}.code_files cf ON cc.file_id = cf.id
                        WHERE cf.repository_id = (SELECT id FROM {schema_name}.repositories WHERE repo_name = :repo_name)
                    """), {'repo_name': repo_row[0]}).fetchone()[0]
                    
                    repos.append({
                        'repo_name': repo_row[0],
                        'repo_url': repo_row[1],
                        'status': repo_row[2],
                        'created_at': repo_row[3].isoformat() if repo_row[3] else None,
                        'updated_at': repo_row[4].isoformat() if repo_row[4] else None,
                        'file_count': file_count,
                        'chunk_count': chunk_count,
                        'schema_name': schema_name
                    })
                    
            except Exception as e:
                logger.error(f"Error getting repositories from schema {schema_name}: {e}")
                continue
    
    return repos

@app.delete("/api/user/{username}/repo/{repo_name}")
async def delete_repository(username: str, repo_name: str):
    """Delete a repository and its data"""
    try:
        schema_name = db_manager.get_user_schema_name(username, repo_name)
        
        with db_manager.get_session(schema_name) as db:
            # Delete repository (cascades to files and chunks)
            db.execute(text(f"""
                DELETE FROM {schema_name}.repositories 
                WHERE repo_name = :repo_name
            """), {'repo_name': repo_name})
            db.commit()
        
        return {"message": f"Repository {repo_name} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 