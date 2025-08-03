#!/usr/bin/env python3

"""
Test script to verify the Code Vectorizer setup
"""

import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def test_imports():
    """Test if all required modules can be imported"""
    console.print("[yellow]Testing imports...[/yellow]")
    
    try:
        import psycopg2
        console.print("[green]✅ psycopg2[/green]")
    except ImportError as e:
        console.print(f"[red]❌ psycopg2: {e}[/red]")
        return False
    
    try:
        import sqlalchemy
        console.print("[green]✅ sqlalchemy[/green]")
    except ImportError as e:
        console.print(f"[red]❌ sqlalchemy: {e}[/red]")
        return False
    
    try:
        import git
        console.print("[green]✅ gitpython[/green]")
    except ImportError as e:
        console.print(f"[red]❌ gitpython: {e}[/red]")
        return False
    
    try:
        import openai
        console.print("[green]✅ openai[/green]")
    except ImportError as e:
        console.print(f"[red]❌ openai: {e}[/red]")
        return False
    
    try:
        import tiktoken
        console.print("[green]✅ tiktoken[/green]")
    except ImportError as e:
        console.print(f"[red]❌ tiktoken: {e}[/red]")
        return False
    
    try:
        import click
        console.print("[green]✅ click[/green]")
    except ImportError as e:
        console.print(f"[red]❌ click: {e}[/red]")
        return False
    
    try:
        import rich
        console.print("[green]✅ rich[/green]")
    except ImportError as e:
        console.print(f"[red]❌ rich: {e}[/red]")
        return False
    
    return True

def test_config():
    """Test configuration loading"""
    console.print("\n[yellow]Testing configuration...[/yellow]")
    
    try:
        from config import Config
        console.print("[green]✅ Configuration loaded[/green]")
        
        # Check required config
        if not Config.OPENAI_API_KEY:
            console.print("[red]❌ OPENAI_API_KEY not set[/red]")
            return False
        
        console.print("[green]✅ OPENAI_API_KEY configured[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        return False

def test_database():
    """Test database connection"""
    console.print("\n[yellow]Testing database connection...[/yellow]")
    
    try:
        from database import test_connection, init_db
        
        if test_connection():
            console.print("[green]✅ Database connection successful[/green]")
            
            # Test table creation
            init_db()
            console.print("[green]✅ Database tables created[/green]")
            return True
        else:
            console.print("[red]❌ Database connection failed[/red]")
            return False
            
    except Exception as e:
        console.print(f"[red]❌ Database error: {e}[/red]")
        return False

def test_openai():
    """Test OpenAI API connection"""
    console.print("\n[yellow]Testing OpenAI API...[/yellow]")
    
    try:
        from embedding_service import EmbeddingService
        
        embedding_service = EmbeddingService()
        if embedding_service.test_connection():
            console.print("[green]✅ OpenAI API connection successful[/green]")
            return True
        else:
            console.print("[red]❌ OpenAI API connection failed[/red]")
            return False
            
    except Exception as e:
        console.print(f"[red]❌ OpenAI API error: {e}[/red]")
        return False

def test_git():
    """Test Git functionality"""
    console.print("\n[yellow]Testing Git functionality...[/yellow]")
    
    try:
        from git_manager import GitManager
        
        git_manager = GitManager()
        console.print("[green]✅ Git manager initialized[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Git error: {e}[/red]")
        return False

def main():
    """Run all tests"""
    console.print(Panel.fit(
        "[bold blue]Code Vectorizer Setup Test[/bold blue]\n"
        "Testing all components for proper setup",
        border_style="blue"
    ))
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Database", test_database),
        ("OpenAI API", test_openai),
        ("Git", test_git)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            console.print(f"[red]❌ {test_name} test failed with exception: {e}[/red]")
            results.append((test_name, False))
    
    # Summary
    console.print("\n[bold]Test Summary:[/bold]")
    
    summary_table = Table()
    summary_table.add_column("Component", style="cyan")
    summary_table.add_column("Status", style="green")
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        style = "green" if result else "red"
        summary_table.add_row(test_name, f"[{style}]{status}[/{style}]")
        
        if not result:
            all_passed = False
    
    console.print(summary_table)
    
    if all_passed:
        console.print("\n[bold green]🎉 All tests passed! Your setup is ready.[/bold green]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("1. Run: python main.py vectorize --repo-url <your-repo-url>")
        console.print("2. Run: python search.py semantic 'your search query'")
    else:
        console.print("\n[bold red]❌ Some tests failed. Please fix the issues above.[/bold red]")
        console.print("\n[bold]Common fixes:[/bold]")
        console.print("1. Install missing packages: pip install -r requirements.txt")
        console.print("2. Set up environment variables: cp env.example .env")
        console.print("3. Start database: docker-compose up -d")
        console.print("4. Add your OpenAI API key to .env file")

if __name__ == '__main__':
    main() 