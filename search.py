#!/usr/bin/env python3

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from database import SessionLocal, CodeChunk, CodeFile, Repository
from embedding_service import EmbeddingService
from sqlalchemy import func
import numpy as np

console = Console()

class CodeSearch:
    def __init__(self):
        self.embedding_service = EmbeddingService()
    
    def search_similar_code(self, query: str, repo_name: str = None, limit: int = 10, similarity_threshold: float = 0.7):
        """Search for similar code chunks"""
        try:
            # Get query embedding
            query_embedding = self.embedding_service.get_embedding(query)
            if not query_embedding:
                console.print("[red]Failed to generate query embedding[/red]")
                return []
            
            # Convert to numpy array for pgvector
            query_vector = np.array(query_embedding)
            
            db = SessionLocal()
            
            # Build query
            query_builder = db.query(
                CodeChunk.content,
                CodeChunk.start_line,
                CodeChunk.end_line,
                CodeChunk.token_count,
                CodeFile.file_path,
                CodeFile.file_name,
                Repository.repo_name,
                1 - func.cosine_similarity(CodeChunk.embedding, query_vector).label('similarity')
            ).join(CodeFile).join(Repository)
            
            if repo_name:
                query_builder = query_builder.filter(Repository.repo_name == repo_name)
            
            # Filter by similarity threshold and order by similarity
            results = query_builder.filter(
                1 - func.cosine_similarity(CodeChunk.embedding, query_vector) > similarity_threshold
            ).order_by(
                func.cosine_similarity(CodeChunk.embedding, query_vector).desc()
            ).limit(limit).all()
            
            return results
            
        except Exception as e:
            console.print(f"[red]Search error: {e}[/red]")
            return []
        finally:
            db.close()
    
    def search_by_file_pattern(self, pattern: str, repo_name: str = None, limit: int = 20):
        """Search for code chunks in files matching a pattern"""
        try:
            db = SessionLocal()
            
            query_builder = db.query(
                CodeChunk.content,
                CodeChunk.start_line,
                CodeChunk.end_line,
                CodeChunk.token_count,
                CodeFile.file_path,
                CodeFile.file_name,
                Repository.repo_name
            ).join(CodeFile).join(Repository)
            
            if repo_name:
                query_builder = query_builder.filter(Repository.repo_name == repo_name)
            
            # Filter by file pattern
            results = query_builder.filter(
                CodeFile.file_path.ilike(f'%{pattern}%')
            ).limit(limit).all()
            
            return results
            
        except Exception as e:
            console.print(f"[red]Search error: {e}[/red]")
            return []
        finally:
            db.close()

@click.group()
def search_cli():
    """Code Search - Search vectorized codebases"""
    pass

@search_cli.command()
@click.argument('query')
@click.option('--repo-name', help='Repository name to search in')
@click.option('--limit', default=10, help='Number of results to return')
@click.option('--threshold', default=0.7, help='Similarity threshold (0.0-1.0)')
def semantic(query, repo_name, limit, threshold):
    """Search for semantically similar code"""
    try:
        console.print(Panel.fit(
            "[bold blue]Code Search[/bold blue]\n"
            "Semantic search in vectorized codebases",
            border_style="blue"
        ))
        
        search = CodeSearch()
        results = search.search_similar_code(query, repo_name, limit, threshold)
        
        if not results:
            console.print("[yellow]No results found[/yellow]")
            return
        
        # Display results
        table = Table(title=f"Search Results for: '{query}'")
        table.add_column("Repository", style="cyan")
        table.add_column("File", style="green")
        table.add_column("Lines", style="yellow")
        table.add_column("Similarity", style="magenta")
        table.add_column("Content Preview", style="white")
        
        for content, start_line, end_line, token_count, file_path, file_name, repo_name, similarity in results:
            # Truncate content for display
            content_preview = content[:100] + "..." if len(content) > 100 else content
            
            table.add_row(
                repo_name,
                f"{file_path}:{start_line}-{end_line}",
                f"{start_line}-{end_line}",
                f"{similarity:.3f}",
                content_preview
            )
        
        console.print(table)
        
        # Show detailed results
        console.print("\n[bold]Detailed Results:[/bold]")
        for i, (content, start_line, end_line, token_count, file_path, file_name, repo_name, similarity) in enumerate(results, 1):
            console.print(f"\n[bold cyan]{i}. {repo_name}/{file_path}:{start_line}-{end_line}[/bold cyan]")
            console.print(f"[yellow]Similarity: {similarity:.3f}[/yellow]")
            console.print(f"[green]Tokens: {token_count}[/green]")
            console.print(f"[white]{content}[/white]")
            console.print("-" * 80)
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@search_cli.command()
@click.argument('pattern')
@click.option('--repo-name', help='Repository name to search in')
@click.option('--limit', default=20, help='Number of results to return')
def files(pattern, repo_name, limit):
    """Search for code in files matching a pattern"""
    try:
        console.print(Panel.fit(
            "[bold blue]File Search[/bold blue]\n"
            "Search code in files matching pattern",
            border_style="blue"
        ))
        
        search = CodeSearch()
        results = search.search_by_file_pattern(pattern, repo_name, limit)
        
        if not results:
            console.print("[yellow]No results found[/yellow]")
            return
        
        # Display results
        table = Table(title=f"File Search Results for: '{pattern}'")
        table.add_column("Repository", style="cyan")
        table.add_column("File", style="green")
        table.add_column("Lines", style="yellow")
        table.add_column("Tokens", style="magenta")
        table.add_column("Content Preview", style="white")
        
        for content, start_line, end_line, token_count, file_path, file_name, repo_name in results:
            # Truncate content for display
            content_preview = content[:100] + "..." if len(content) > 100 else content
            
            table.add_row(
                repo_name,
                file_path,
                f"{start_line}-{end_line}",
                str(token_count),
                content_preview
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")

@search_cli.command()
def list_repos():
    """List available repositories for search"""
    try:
        db = SessionLocal()
        repos = db.query(Repository).filter(Repository.status == 'completed').all()
        
        if not repos:
            console.print("[yellow]No completed repositories found[/yellow]")
            return
        
        table = Table(title="Available Repositories for Search")
        table.add_column("Name", style="cyan")
        table.add_column("URL", style="green")
        table.add_column("Files", style="yellow")
        table.add_column("Chunks", style="magenta")
        
        for repo in repos:
            file_count = db.query(CodeFile).filter(CodeFile.repository_id == repo.id).count()
            chunk_count = db.query(CodeChunk).join(CodeFile).filter(CodeFile.repository_id == repo.id).count()
            
            table.add_row(
                repo.repo_name,
                repo.repo_url,
                str(file_count),
                str(chunk_count)
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
    finally:
        db.close()

if __name__ == '__main__':
    search_cli() 