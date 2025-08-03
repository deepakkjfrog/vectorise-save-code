import os
import tempfile
import hashlib
from pathlib import Path
from git import Repo, GitCommandError
from config import Config
import logging

logger = logging.getLogger(__name__)

class GitManager:
    def __init__(self, github_token=None, github_username=None):
        self.github_token = github_token or Config.GITHUB_TOKEN
        self.github_username = github_username or Config.GITHUB_USERNAME
        self.temp_dir = Path(tempfile.gettempdir()) / "vectorize_repos"
        self.temp_dir.mkdir(exist_ok=True)
    
    def _get_auth_url(self, repo_url):
        """Convert public repo URL to authenticated URL"""
        if not self.github_token:
            return repo_url
        
        # Handle different GitHub URL formats
        if repo_url.startswith('https://github.com/'):
            return repo_url.replace('https://github.com/', f'https://{self.github_token}@github.com/')
        elif repo_url.startswith('git@github.com:'):
            return repo_url
        
        return repo_url
    
    def clone_repository(self, repo_url, repo_name):
        """Clone a repository to a temporary directory"""
        try:
            # Create unique directory for this repository
            repo_dir = self.temp_dir / repo_name
            if repo_dir.exists():
                logger.info(f"Repository {repo_name} already exists, removing old clone")
                import shutil
                shutil.rmtree(repo_dir)
            
            repo_dir.mkdir(exist_ok=True)
            
            # Get authenticated URL
            auth_url = self._get_auth_url(repo_url)
            
            logger.info(f"Cloning repository: {repo_name}")
            logger.info(f"URL: {repo_url}")
            logger.info(f"Target directory: {repo_dir}")
            
            # Clone the repository
            repo = Repo.clone_from(auth_url, repo_dir)
            
            logger.info(f"Successfully cloned repository: {repo_name}")
            logger.info(f"Branch: {repo.active_branch.name}")
            logger.info(f"Commit: {repo.head.commit.hexsha[:8]}")
            
            return str(repo_dir)
            
        except GitCommandError as e:
            logger.error(f"Git command error while cloning {repo_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error cloning repository {repo_name}: {e}")
            raise
    
    def get_repository_info(self, repo_path):
        """Get information about the cloned repository"""
        try:
            repo = Repo(repo_path)
            return {
                'branch': repo.active_branch.name,
                'commit_hash': repo.head.commit.hexsha,
                'commit_message': repo.head.commit.message,
                'author': repo.head.commit.author.name,
                'committed_date': repo.head.commit.committed_datetime,
                'remote_url': repo.remotes.origin.url if repo.remotes else None
            }
        except Exception as e:
            logger.error(f"Error getting repository info: {e}")
            return {}
    
    def cleanup_repository(self, repo_path):
        """Remove cloned repository"""
        try:
            import shutil
            if os.path.exists(repo_path):
                shutil.rmtree(repo_path)
                logger.info(f"Cleaned up repository: {repo_path}")
        except Exception as e:
            logger.error(f"Error cleaning up repository {repo_path}: {e}")
    
    def get_file_content_hash(self, file_path):
        """Calculate SHA256 hash of file content"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash for {file_path}: {e}")
            return None 