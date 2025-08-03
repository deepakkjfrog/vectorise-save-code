import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Database configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://vectorize_user:vectorize_password@localhost:5432/vectorize_db')
    
    # OpenAI configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'text-embedding-ada-002')
    
    # Git configuration
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
    
    # Application configuration
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1000'))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '200'))
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '1024 * 1024'))  # 1MB
    
    # Supported file extensions for code files
    SUPPORTED_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
        '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.clj',
        '.hs', '.ml', '.fs', '.sql', '.sh', '.bash', '.zsh', '.fish', '.ps1',
        '.r', '.m', '.scm', '.lisp', '.el', '.vim', '.tex', '.md', '.rst',
        '.yaml', '.yml', '.json', '.xml', '.html', '.css', '.scss', '.sass',
        '.vue', '.svelte', '.astro', '.toml', '.ini', '.cfg', '.conf'
    }
    
    # File patterns to ignore
    IGNORE_PATTERNS = {
        '__pycache__', '.git', '.svn', '.hg', '.DS_Store', 'node_modules',
        'vendor', 'dist', 'build', 'target', '.idea', '.vscode', '*.log',
        '*.tmp', '*.temp', '*.swp', '*.swo', '*.bak', '*.orig'
    } 