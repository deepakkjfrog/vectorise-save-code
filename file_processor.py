import os
import re
from pathlib import Path
from typing import List, Dict, Generator, Tuple
import tiktoken
from config import Config
import logging

logger = logging.getLogger(__name__)

class FileProcessor:
    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")  # OpenAI tokenizer
        self.supported_extensions = Config.SUPPORTED_EXTENSIONS
        self.ignore_patterns = Config.IGNORE_PATTERNS
        self.chunk_size = Config.CHUNK_SIZE
        self.chunk_overlap = Config.CHUNK_OVERLAP
        self.max_file_size = Config.MAX_FILE_SIZE
    
    def should_ignore_file(self, file_path: str) -> bool:
        """Check if file should be ignored based on patterns"""
        path_parts = Path(file_path).parts
        
        # Check for ignore patterns in path
        for part in path_parts:
            if part in self.ignore_patterns:
                return True
        
        # Check file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.supported_extensions:
            return True
        
        return False
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0
    
    def is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary"""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\x00' in chunk
        except Exception:
            return True
    
    def discover_code_files(self, repo_path: str) -> List[Dict]:
        """Discover all code files in the repository"""
        code_files = []
        repo_path_obj = Path(repo_path)
        
        logger.info(f"Discovering code files in: {repo_path}")
        
        for file_path in repo_path_obj.rglob('*'):
            if file_path.is_file():
                relative_path = str(file_path.relative_to(repo_path))
                
                # Check if file should be ignored
                if self.should_ignore_file(relative_path):
                    continue
                
                # Check file size
                file_size = self.get_file_size(str(file_path))
                if file_size > self.max_file_size:
                    logger.warning(f"Skipping large file: {relative_path} ({file_size} bytes)")
                    continue
                
                # Check if binary
                if self.is_binary_file(str(file_path)):
                    logger.warning(f"Skipping binary file: {relative_path}")
                    continue
                
                code_files.append({
                    'file_path': relative_path,
                    'file_name': file_path.name,
                    'file_extension': file_path.suffix.lower(),
                    'file_size': file_size,
                    'absolute_path': str(file_path)
                })
        
        logger.info(f"Found {len(code_files)} code files")
        return code_files
    
    def read_file_content(self, file_path: str) -> str:
        """Read file content with proper encoding handling"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return ""
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using OpenAI tokenizer"""
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            return len(text.split())  # Fallback to word count
    
    def chunk_text(self, text: str, file_path: str) -> List[Dict]:
        """Split text into chunks with overlap"""
        if not text.strip():
            return []
        
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_line_start = 1
        current_tokens = 0
        
        for i, line in enumerate(lines, 1):
            line_tokens = self.count_tokens(line + '\n')
            
            # If adding this line would exceed chunk size, save current chunk
            if current_tokens + line_tokens > self.chunk_size and current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    'content': chunk_text,
                    'start_line': current_line_start,
                    'end_line': i - 1,
                    'token_count': current_tokens,
                    'file_path': file_path
                })
                
                # Start new chunk with overlap
                overlap_lines = []
                overlap_tokens = 0
                for j in range(len(current_chunk) - 1, -1, -1):
                    line_tokens = self.count_tokens(current_chunk[j] + '\n')
                    if overlap_tokens + line_tokens <= self.chunk_overlap:
                        overlap_lines.insert(0, current_chunk[j])
                        overlap_tokens += line_tokens
                    else:
                        break
                
                current_chunk = overlap_lines
                current_tokens = overlap_tokens
                current_line_start = i - len(overlap_lines)
            
            current_chunk.append(line)
            current_tokens += line_tokens
        
        # Add final chunk if not empty
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'content': chunk_text,
                'start_line': current_line_start,
                'end_line': len(lines),
                'token_count': current_tokens,
                'file_path': file_path
            })
        
        return chunks
    
    def process_file(self, file_path: str) -> List[Dict]:
        """Process a single file and return chunks"""
        try:
            content = self.read_file_content(file_path)
            if not content.strip():
                return []
            
            chunks = self.chunk_text(content, file_path)
            logger.info(f"Processed {file_path}: {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return [] 