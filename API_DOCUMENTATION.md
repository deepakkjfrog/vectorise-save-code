# Code Vectorizer API Documentation

## Overview

The Code Vectorizer API is a RESTful service that allows you to vectorize codebases and perform semantic search on code. It supports multiple users with isolated data storage using dynamic database schemas.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, the API uses username-based identification. Each user's data is isolated in separate database schemas.

## API Endpoints

### 1. Health Check

**GET** `/api/health`

Check if the API is running.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### 2. Vectorize Repository

**POST** `/api/vectorize`

Start vectorizing a Git repository.

**Request Body:**
```json
{
  "repo_url": "https://github.com/username/repo-name",
  "username": "john_doe",
  "repo_name": "my-repo",
  "github_token": "ghp_xxxxxxxxxxxx",
  "github_username": "github_username",
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "max_file_size": 1048576
}
```

**Parameters:**
- `repo_url` (required): GitHub repository URL
- `username` (required): User identifier for data isolation
- `repo_name` (optional): Custom repository name (defaults to extracted from URL)
- `github_token` (optional): GitHub token for private repositories
- `github_username` (optional): GitHub username
- `chunk_size` (optional): Maximum tokens per chunk (default: 1000)
- `chunk_overlap` (optional): Token overlap between chunks (default: 200)
- `max_file_size` (optional): Maximum file size in bytes (default: 1048576)

**Response:**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "pending",
  "message": "Vectorization job started",
  "created_at": "2024-01-15T10:30:00.000Z"
}
```

### 3. Get Job Status

**GET** `/api/job/{job_id}`

Get the status and progress of a vectorization job.

**Response:**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "processing",
  "progress": {
    "step": "generating_embeddings",
    "files_discovered": 150,
    "files_processed": 150,
    "chunks_created": 1200,
    "chunks_with_embeddings": 800,
    "chunks_saved": 0,
    "current_file": "main.py"
  },
  "created_at": "2024-01-15T10:30:00.000Z",
  "updated_at": "2024-01-15T10:35:00.000Z",
  "error": null
}
```

**Status Values:**
- `pending`: Job is queued
- `processing`: Job is running
- `completed`: Job finished successfully
- `failed`: Job failed with error

### 4. Search Code

**POST** `/api/search`

Search for code using semantic similarity.

**Request Body:**
```json
{
  "query": "function to parse JSON",
  "username": "john_doe",
  "repo_name": "my-repo",
  "limit": 10,
  "similarity_threshold": 0.7
}
```

**Parameters:**
- `query` (required): Search query text
- `username` (required): User identifier
- `repo_name` (optional): Search in specific repository only
- `limit` (optional): Maximum results to return (default: 10)
- `similarity_threshold` (optional): Minimum similarity score (default: 0.7)

**Response:**
```json
{
  "results": [
    {
      "content": "def parse_json(data):\n    return json.loads(data)",
      "start_line": 15,
      "end_line": 16,
      "token_count": 45,
      "file_path": "utils.py",
      "file_name": "utils.py",
      "repo_name": "my-repo",
      "similarity": 0.892
    }
  ],
  "total": 1,
  "query": "function to parse JSON"
}
```

### 5. Get User Repositories

**GET** `/api/user/{username}/repos`

Get all repositories for a user.

**Response:**
```json
{
  "username": "john_doe",
  "repositories": [
    {
      "repo_name": "my-repo",
      "repo_url": "https://github.com/username/repo-name",
      "status": "completed",
      "created_at": "2024-01-15T10:30:00.000Z",
      "updated_at": "2024-01-15T10:45:00.000Z",
      "file_count": 150,
      "chunk_count": 1200,
      "schema_name": "user_john_doe_repo_my_repo"
    }
  ]
}
```

### 6. Delete Repository

**DELETE** `/api/user/{username}/repo/{repo_name}`

Delete a repository and all its vectorized data.

**Response:**
```json
{
  "message": "Repository my-repo deleted successfully"
}
```

## Database Schema

Each user's repositories are stored in separate PostgreSQL schemas with the naming pattern:
```
user_{username}_repo_{repo_name}
```

### Tables in each schema:

1. **repositories**: Repository metadata
2. **code_files**: File information and content hashes
3. **code_chunks**: Code chunks with vector embeddings

## Usage Examples

### Python Client

```python
import requests

# Start vectorization
response = requests.post("http://localhost:8000/api/vectorize", json={
    "repo_url": "https://github.com/username/repo",
    "username": "john_doe"
})

job_id = response.json()["job_id"]

# Check status
status = requests.get(f"http://localhost:8000/api/job/{job_id}").json()

# Search code
search_results = requests.post("http://localhost:8000/api/search", json={
    "query": "authentication function",
    "username": "john_doe"
}).json()
```

### cURL Examples

```bash
# Vectorize repository
curl -X POST "http://localhost:8000/api/vectorize" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/username/repo",
    "username": "john_doe"
  }'

# Check job status
curl "http://localhost:8000/api/job/a1b2c3d4e5f6"

# Search code
curl -X POST "http://localhost:8000/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection",
    "username": "john_doe"
  }'
```

## Error Handling

The API returns standard HTTP status codes:

- `200`: Success
- `400`: Bad Request (invalid parameters)
- `404`: Not Found (job or repository not found)
- `500`: Internal Server Error

Error responses include a detail message:

```json
{
  "detail": "Repository not found"
}
```

## Rate Limiting

Currently, there are no rate limits implemented. Consider implementing rate limiting for production use.

## Security Considerations

1. **Authentication**: Implement proper authentication (JWT, API keys, etc.)
2. **Authorization**: Add user authorization checks
3. **Input Validation**: Validate all input parameters
4. **Rate Limiting**: Implement rate limiting for production
5. **HTTPS**: Use HTTPS in production
6. **Secrets Management**: Store API keys and tokens securely

## Performance

- Vectorization jobs run asynchronously in the background
- Database queries use indexes for optimal performance
- Vector similarity search uses pgvector's IVFFlat index
- Large repositories are processed in chunks to manage memory

## Monitoring

Monitor the following metrics:
- Job completion rates
- Processing times
- Error rates
- Database performance
- API response times

## Deployment

### Development
```bash
make server-dev
```

### Production
```bash
# Using uvicorn
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4

# Using gunicorn
gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker
```bash
# Build image
docker build -t code-vectorizer .

# Run container
docker run -p 8000:8000 code-vectorizer
```

## API Documentation UI

Access interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc` 