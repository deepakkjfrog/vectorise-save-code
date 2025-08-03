from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from database import SessionLocal, Repository, CodeFile, CodeChunk, init_db, test_connection
from git_manager import GitManager
from file_processor import FileProcessor
from embedding_service import EmbeddingService
from config import Config
import logging
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import time

console = Console()
logger = logging.getLogger(__name__)

class CodeVectorizer:
    def __init__(self, github_token: Optional[str] = None, github_username: Optional[str] = None):
        self.git_manager = GitManager(github_token, github_username)
        self.file_processor = FileProcessor()
        self.embedding_service = EmbeddingService()
        
        # Initialize database
        init_db()
        
        if not test_connection():
            raise Exception("Database connection failed")
        
        if not self.embedding_service.test_connection():
            raise Exception("OpenAI API connection failed")
    
    def vectorize_repository(self, repo_url: str, repo_name: Optional[str] = None) -> Dict:
        """Main method to vectorize a repository"""
        if not repo_name:
            repo_name = repo_url.split('/')[-1].replace('.git', '')
        
        console.print(f"[bold blue]Starting vectorization of repository: {repo_name}[/bold blue]")
        
        try:
            # Step 1: Clone repository
            console.print("[yellow]Step 1: Cloning repository...[/yellow]")
            clone_path = self.git_manager.clone_repository(repo_url, repo_name)
            
            # Step 2: Save repository to database
            console.print("[yellow]Step 2: Saving repository to database...[/yellow]")
            repo_info = self.git_manager.get_repository_info(clone_path)
            db_repo = self._save_repository(repo_url, repo_name, clone_path)
            
            # Step 3: Discover code files
            console.print("[yellow]Step 3: Discovering code files...[/yellow]")
            code_files = self.file_processor.discover_code_files(clone_path)
            
            if not code_files:
                console.print("[red]No code files found in repository[/red]")
                return {"status": "error", "message": "No code files found"}
            
            # Step 4: Process files and create chunks
            console.print("[yellow]Step 4: Processing files and creating chunks...[/yellow]")
            all_chunks = []
            processed_files = []
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Processing files...", total=len(code_files))
                
                for file_info in code_files:
                    progress.update(task, description=f"Processing {file_info['file_name']}")
                    
                    # Process file and get chunks
                    chunks = self.file_processor.process_file(file_info['absolute_path'])
                    
                    if chunks:
                        # Add file info to chunks
                        for chunk in chunks:
                            chunk['file_info'] = file_info
                        
                        all_chunks.extend(chunks)
                        processed_files.append(file_info)
                    
                    progress.advance(task)
            
            # Step 5: Save files to database
            console.print("[yellow]Step 5: Saving files to database...[/yellow]")
            file_mapping = self._save_files(db_repo.id, processed_files)
            
            # Step 6: Generate embeddings
            console.print("[yellow]Step 6: Generating embeddings...[/yellow]")
            processed_chunks = self.embedding_service.process_chunks(all_chunks)
            
            if not processed_chunks:
                console.print("[red]No chunks with embeddings generated[/red]")
                return {"status": "error", "message": "Failed to generate embeddings"}
            
            # Step 7: Save chunks and embeddings to database
            console.print("[yellow]Step 7: Saving chunks and embeddings to database...[/yellow]")
            saved_chunks = self._save_chunks(file_mapping, processed_chunks)
            
            # Step 8: Update repository status
            self._update_repository_status(db_repo.id, 'completed')
            
            # Step 9: Cleanup
            console.print("[yellow]Step 8: Cleaning up...[/yellow]")
            self.git_manager.cleanup_repository(clone_path)
            
            # Summary
            summary = {
                "status": "success",
                "repository": {
                    "id": db_repo.id,
                    "name": repo_name,
                    "url": repo_url,
                    "info": repo_info
                },
                "files": {
                    "total_discovered": len(code_files),
                    "processed": len(processed_files)
                },
                "chunks": {
                    "total_created": len(all_chunks),
                    "with_embeddings": len(processed_chunks),
                    "saved": saved_chunks
                }
            }
            
            console.print(f"[bold green]Vectorization completed successfully![/bold green]")
            console.print(f"Repository: {repo_name}")
            console.print(f"Files processed: {len(processed_files)}/{len(code_files)}")
            console.print(f"Chunks with embeddings: {len(processed_chunks)}/{len(all_chunks)}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error vectorizing repository {repo_name}: {e}")
            console.print(f"[bold red]Error vectorizing repository: {e}[/bold red]")
            
            # Update repository status to failed
            if 'db_repo' in locals():
                self._update_repository_status(db_repo.id, 'failed')
            
            return {"status": "error", "message": str(e)}
    
    def _save_repository(self, repo_url: str, repo_name: str, clone_path: str) -> Repository:
        """Save repository information to database"""
        db = SessionLocal()
        try:
            # Check if repository already exists
            existing_repo = db.query(Repository).filter(Repository.repo_name == repo_name).first()
            if existing_repo:
                # Update existing repository
                existing_repo.repo_url = repo_url
                existing_repo.clone_path = clone_path
                existing_repo.status = 'processing'
                db.commit()
                return existing_repo
            
            # Create new repository
            repo = Repository(
                repo_name=repo_name,
                repo_url=repo_url,
                clone_path=clone_path,
                status='processing'
            )
            db.add(repo)
            db.commit()
            db.refresh(repo)
            return repo
            
        finally:
            db.close()
    
    def _save_files(self, repo_id: int, files: List[Dict]) -> Dict[str, int]:
        """Save code files to database and return file_id mapping"""
        db = SessionLocal()
        file_mapping = {}
        
        try:
            for file_info in files:
                # Calculate content hash
                content_hash = self.git_manager.get_file_content_hash(file_info['absolute_path'])
                
                # Check if file already exists
                existing_file = db.query(CodeFile).filter(
                    CodeFile.repository_id == repo_id,
                    CodeFile.file_path == file_info['file_path']
                ).first()
                
                if existing_file:
                    # Update existing file
                    existing_file.file_size = file_info['file_size']
                    existing_file.content_hash = content_hash
                    file_mapping[file_info['file_path']] = existing_file.id
                else:
                    # Create new file
                    code_file = CodeFile(
                        repository_id=repo_id,
                        file_path=file_info['file_path'],
                        file_name=file_info['file_name'],
                        file_extension=file_info['file_extension'],
                        file_size=file_info['file_size'],
                        content_hash=content_hash
                    )
                    db.add(code_file)
                    db.commit()
                    db.refresh(code_file)
                    file_mapping[file_info['file_path']] = code_file.id
            
            return file_mapping
            
        finally:
            db.close()
    
    def _save_chunks(self, file_mapping: Dict[str, int], chunks: List[Dict]) -> int:
        """Save code chunks with embeddings to database"""
        db = SessionLocal()
        saved_count = 0
        
        try:
            for chunk in chunks:
                file_path = chunk['file_info']['file_path']
                file_id = file_mapping.get(file_path)
                
                if file_id is None:
                    logger.warning(f"File ID not found for {file_path}")
                    continue
                
                # Create code chunk
                code_chunk = CodeChunk(
                    file_id=file_id,
                    chunk_index=chunk.get('chunk_index', 0),
                    content=chunk['content'],
                    start_line=chunk['start_line'],
                    end_line=chunk['end_line'],
                    token_count=chunk['token_count'],
                    embedding=chunk['embedding']
                )
                
                db.add(code_chunk)
                saved_count += 1
            
            db.commit()
            return saved_count
            
        finally:
            db.close()
    
    def _update_repository_status(self, repo_id: int, status: str):
        """Update repository status"""
        db = SessionLocal()
        try:
            repo = db.query(Repository).filter(Repository.id == repo_id).first()
            if repo:
                repo.status = status
                db.commit()
        finally:
            db.close()
    
    def get_repository_stats(self, repo_name: str) -> Optional[Dict]:
        """Get statistics for a vectorized repository"""
        db = SessionLocal()
        try:
            repo = db.query(Repository).filter(Repository.repo_name == repo_name).first()
            if not repo:
                return None
            
            file_count = db.query(CodeFile).filter(CodeFile.repository_id == repo.id).count()
            chunk_count = db.query(CodeChunk).join(CodeFile).filter(CodeFile.repository_id == repo.id).count()
            
            return {
                "repository": {
                    "id": repo.id,
                    "name": repo.repo_name,
                    "url": repo.repo_url,
                    "status": repo.status,
                    "created_at": repo.created_at.isoformat(),
                    "updated_at": repo.updated_at.isoformat()
                },
                "files": file_count,
                "chunks": chunk_count
            }
            
        finally:
            db.close() 