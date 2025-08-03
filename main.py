#!/usr/bin/env python3

import click
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from vectorizer import CodeVectorizer
from database import SessionLocal, Repository, CodeFile, CodeChunk
from sqlalchemy import func
import json

console = Console()

@click.group()
def cli():
    """Code Vectorizer - Vectorize codebases and store in PostgreSQL with pgvector"""
    pass

@cli.command()
@click.option('--repo-url', required=True, help='GitHub repository URL')
@click.option('--repo-name', help='Repository name (optional, will be extracted from URL)')
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub token for private repositories')
@click.option('--github-username', envvar='GITHUB_USERNAME', help='GitHub username')
def vectorize(repo_url, repo_name, github_token, github_username):
    """Vectorize a GitHub repository"""
    try:
        console.print(Panel.fit(
            "[bold blue]Code Vectorizer[/bold blue]\n"
            "Vectorizing codebases with OpenAI embeddings",
            border_style="blue"
        ))
        
        # Initialize vectorizer
        vectorizer = CodeVectorizer(github_token, github_username)
        
        # Vectorize repository
        result = vectorizer.vectorize_repository(repo_url, repo_name)
        
        if result["status"] == "success":
            console.print(f"\n[bold green]✅ Vectorization completed successfully![/bold green]")
            
            # Display summary
            summary_table = Table(title="Vectorization Summary")
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="green")
            
            summary_table.add_row("Repository", result["repository"]["name"])
            summary_table.add_row("Files Discovered", str(result["files"]["total_discovered"]))
            summary_table.add_row("Files Processed", str(result["files"]["processed"]))
            summary_table.add_row("Chunks Created", str(result["chunks"]["total_created"]))
            summary_table.add_row("Chunks with Embeddings", str(result["chunks"]["with_embeddings"]))
            summary_table.add_row("Chunks Saved", str(result["chunks"]["saved"]))
            
            console.print(summary_table)
        else:
            console.print(f"\n[bold red]❌ Vectorization failed: {result['message']}[/bold red]")
            
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]")

@cli.command()
def list_repos():
    """List all vectorized repositories"""
    try:
        db = SessionLocal()
        repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
        
        if not repos:
            console.print("[yellow]No repositories found[/yellow]")
            return
        
        table = Table(title="Vectorized Repositories")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Files", style="blue")
        table.add_column("Chunks", style="magenta")
        table.add_column("Created", style="white")
        
        for repo in repos:
            file_count = db.query(CodeFile).filter(CodeFile.repository_id == repo.id).count()
            chunk_count = db.query(CodeChunk).join(CodeFile).filter(CodeFile.repository_id == repo.id).count()
            
            status_color = "green" if repo.status == "completed" else "red" if repo.status == "failed" else "yellow"
            
            table.add_row(
                str(repo.id),
                repo.repo_name,
                f"[{status_color}]{repo.status}[/{status_color}]",
                str(file_count),
                str(chunk_count),
                repo.created_at.strftime("%Y-%m-%d %H:%M")
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
    finally:
        db.close()

@cli.command()
@click.argument('repo_name')
def stats(repo_name):
    """Get detailed statistics for a repository"""
    try:
        db = SessionLocal()
        repo = db.query(Repository).filter(Repository.repo_name == repo_name).first()
        
        if not repo:
            console.print(f"[red]Repository '{repo_name}' not found[/red]")
            return
        
        # Get file statistics
        file_stats = db.query(
            CodeFile.file_extension,
            func.count(CodeFile.id).label('count'),
            func.sum(CodeFile.file_size).label('total_size')
        ).filter(CodeFile.repository_id == repo.id).group_by(CodeFile.file_extension).all()
        
        # Get chunk statistics
        chunk_count = db.query(CodeChunk).join(CodeFile).filter(CodeFile.repository_id == repo.id).count()
        
        console.print(Panel.fit(
            f"[bold blue]Repository Statistics[/bold blue]\n"
            f"Name: {repo.repo_name}\n"
            f"Status: {repo.status}\n"
            f"Created: {repo.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Updated: {repo.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            border_style="blue"
        ))
        
        # File statistics table
        file_table = Table(title="File Statistics by Extension")
        file_table.add_column("Extension", style="cyan")
        file_table.add_column("Count", style="green")
        file_table.add_column("Total Size (KB)", style="blue")
        
        for ext, count, size in file_stats:
            size_kb = (size or 0) / 1024
            file_table.add_row(ext or "No extension", str(count), f"{size_kb:.1f}")
        
        console.print(file_table)
        
        # Chunk statistics
        console.print(f"\n[bold]Total Code Chunks:[/bold] {chunk_count}")
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
    finally:
        db.close()

@cli.command()
@click.argument('repo_name')
def delete(repo_name):
    """Delete a vectorized repository and all its data"""
    try:
        db = SessionLocal()
        repo = db.query(Repository).filter(Repository.repo_name == repo_name).first()
        
        if not repo:
            console.print(f"[red]Repository '{repo_name}' not found[/red]")
            return
        
        # Confirm deletion
        if not click.confirm(f"Are you sure you want to delete repository '{repo_name}' and all its data?"):
            console.print("[yellow]Deletion cancelled[/yellow]")
            return
        
        # Delete repository (cascades to files and chunks)
        db.delete(repo)
        db.commit()
        
        console.print(f"[green]Repository '{repo_name}' deleted successfully[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
    finally:
        db.close()

@cli.command()
def setup():
    """Setup the database and test connections"""
    try:
        console.print("[yellow]Setting up Code Vectorizer...[/yellow]")
        
        # Test database connection
        from database import test_connection
        if test_connection():
            console.print("[green]✅ Database connection successful[/green]")
        else:
            console.print("[red]❌ Database connection failed[/red]")
            return
        
        # Test OpenAI connection
        from embedding_service import EmbeddingService
        embedding_service = EmbeddingService()
        if embedding_service.test_connection():
            console.print("[green]✅ OpenAI API connection successful[/green]")
        else:
            console.print("[red]❌ OpenAI API connection failed[/red]")
            return
        
        console.print("[green]✅ Setup completed successfully![/green]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("1. Use 'vectorize' command to vectorize a repository")
        console.print("2. Use 'list-repos' to see all vectorized repositories")
        console.print("3. Use 'stats <repo-name>' to get detailed statistics")
        
    except Exception as e:
        console.print(f"[bold red]Setup failed: {str(e)}[/bold red]")

if __name__ == '__main__':
    cli() 