#!/usr/bin/env python3

"""
Client example for the Code Vectorizer API
"""

import requests
import json
import time
from typing import Dict, Any

class CodeVectorizerClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
    
    def vectorize_repository(self, 
                           repo_url: str, 
                           username: str, 
                           repo_name: str = None,
                           github_token: str = None,
                           github_username: str = None,
                           chunk_size: int = 1000,
                           chunk_overlap: int = 200,
                           max_file_size: int = 1048576) -> Dict[str, Any]:
        """Start vectorizing a repository"""
        
        payload = {
            "repo_url": repo_url,
            "username": username,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "max_file_size": max_file_size
        }
        
        if repo_name:
            payload["repo_name"] = repo_name
        if github_token:
            payload["github_token"] = github_token
        if github_username:
            payload["github_username"] = github_username
        
        response = requests.post(f"{self.base_url}/api/vectorize", json=payload)
        response.raise_for_status()
        
        return response.json()
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a vectorization job"""
        response = requests.get(f"{self.base_url}/api/job/{job_id}")
        response.raise_for_status()
        
        return response.json()
    
    def wait_for_job_completion(self, job_id: str, poll_interval: int = 5) -> Dict[str, Any]:
        """Wait for a job to complete and return the final status"""
        while True:
            status = self.get_job_status(job_id)
            
            if status["status"] in ["completed", "failed"]:
                return status
            
            print(f"Job {job_id}: {status['status']} - {status['progress']['step']}")
            time.sleep(poll_interval)
    
    def search_code(self, 
                   query: str, 
                   username: str, 
                   repo_name: str = None,
                   limit: int = 10,
                   similarity_threshold: float = 0.7) -> Dict[str, Any]:
        """Search for code using semantic similarity"""
        
        payload = {
            "query": query,
            "username": username,
            "limit": limit,
            "similarity_threshold": similarity_threshold
        }
        
        if repo_name:
            payload["repo_name"] = repo_name
        
        response = requests.post(f"{self.base_url}/api/search", json=payload)
        response.raise_for_status()
        
        return response.json()
    
    def get_user_repositories(self, username: str) -> Dict[str, Any]:
        """Get all repositories for a user"""
        response = requests.get(f"{self.base_url}/api/user/{username}/repos")
        response.raise_for_status()
        
        return response.json()
    
    def delete_repository(self, username: str, repo_name: str) -> Dict[str, Any]:
        """Delete a repository and its data"""
        response = requests.delete(f"{self.base_url}/api/user/{username}/repo/{repo_name}")
        response.raise_for_status()
        
        return response.json()
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        response = requests.get(f"{self.base_url}/api/health")
        response.raise_for_status()
        
        return response.json()

def main():
    """Example usage of the Code Vectorizer API"""
    
    # Initialize client
    client = CodeVectorizerClient("http://localhost:8000")
    
    # Check API health
    try:
        health = client.health_check()
        print(f"✅ API Health: {health['status']}")
    except Exception as e:
        print(f"❌ API not available: {e}")
        return
    
    # Example 1: Vectorize a repository
    print("\n🚀 Example 1: Vectorizing a repository")
    
    try:
        # Start vectorization
        job = client.vectorize_repository(
            repo_url="https://github.com/username/example-repo",
            username="john_doe",
            repo_name="example-repo"
        )
        
        print(f"Job started: {job['job_id']}")
        
        # Wait for completion
        final_status = client.wait_for_job_completion(job['job_id'])
        
        if final_status['status'] == 'completed':
            print("✅ Vectorization completed successfully!")
            print(f"Files processed: {final_status['progress']['files_processed']}")
            print(f"Chunks saved: {final_status['progress']['chunks_saved']}")
        else:
            print(f"❌ Vectorization failed: {final_status.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error vectorizing repository: {e}")
    
    # Example 2: Search for code
    print("\n🔍 Example 2: Searching for code")
    
    try:
        search_results = client.search_code(
            query="function to parse JSON",
            username="john_doe",
            limit=5
        )
        
        print(f"Found {search_results['total']} results:")
        for i, result in enumerate(search_results['results'][:3], 1):
            print(f"\n{i}. {result['repo_name']}/{result['file_path']}:{result['start_line']}-{result['end_line']}")
            print(f"   Similarity: {result['similarity']:.3f}")
            print(f"   Content: {result['content'][:100]}...")
            
    except Exception as e:
        print(f"❌ Error searching code: {e}")
    
    # Example 3: List user repositories
    print("\n📚 Example 3: Listing user repositories")
    
    try:
        repos = client.get_user_repositories("john_doe")
        
        print(f"User {repos['username']} has {len(repos['repositories'])} repositories:")
        for repo in repos['repositories']:
            print(f"  - {repo['repo_name']} ({repo['status']})")
            print(f"    Files: {repo['file_count']}, Chunks: {repo['chunk_count']}")
            
    except Exception as e:
        print(f"❌ Error listing repositories: {e}")

if __name__ == "__main__":
    main() 