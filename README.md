# Code Vectorizer

A powerful tool to vectorize codebases and store them in PostgreSQL with pgvector extension for semantic search and LLM integration.

## Features

- 🔍 **Code Discovery**: Automatically discovers and processes code files from Git repositories
- 🧠 **Smart Chunking**: Intelligent text chunking with configurable overlap for better context
- 🔢 **Vector Embeddings**: Generates embeddings using OpenAI's text-embedding-ada-002 model
- 🗄️ **PostgreSQL Storage**: Stores vectors in PostgreSQL with pgvector for efficient similarity search
- 🐳 **Docker Support**: Easy setup with Docker Compose
- 📊 **Rich CLI**: Beautiful command-line interface with progress tracking and statistics
- 🔐 **Git Authentication**: Support for private repositories with GitHub tokens

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Git Repo      │───▶│  Code Files     │───▶│  Text Chunks    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  PostgreSQL     │    │   OpenAI API    │
                       │  (pgvector)     │◀───│  Embeddings     │
                       └─────────────────┘    └─────────────────┘
```

## Prerequisites

- Docker and Docker Compose
- OpenAI API key
- GitHub token (for private repositories)

## Quick Start

### Option 1: One-Command Setup (Recommended)

```bash
# Clone the repository
git clone <your-repo-url>
cd VectoriseCodeBase

# Run the startup script
./start.sh
```

The script will:
1. Create `.env` file from template
2. Prompt you to add your OpenAI API key
3. Start all services automatically
4. Show you how to use the API

### Option 2: Manual Setup

#### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd VectoriseCodeBase
```

#### 2. Configure Environment

```bash
cp env.example .env
```

Edit `.env` with your OpenAI API key:
```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional (for private repositories)
GITHUB_TOKEN=your_github_token_here
GITHUB_USERNAME=your_github_username_here
```

#### 3. Start Services

```bash
docker-compose up -d
```

#### 4. Verify Setup

```bash
# Check services
docker-compose ps

# Test API
curl http://localhost:8000/api/health
```

### 5. Use the API

#### Interactive Documentation
Visit `http://localhost:8000/docs` for Swagger UI

#### Command Line Examples
```bash
# Vectorize a repository
curl -X POST "http://localhost:8000/api/vectorize" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/username/repo-name",
    "username": "test_user"
  }'

# Search for code
curl -X POST "http://localhost:8000/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "function to parse JSON",
    "username": "test_user"
  }'
```

#### Using Make Commands
```bash
# Vectorize repository
make vectorize REPO_URL=https://github.com/username/repo USERNAME=test_user

# Search code
make search QUERY="authentication function" USERNAME=test_user

# List repositories
make list-repos USERNAME=test_user
```

## Usage

### CLI Interface

#### Vectorize a Repository

```bash
# Public repository
python main.py vectorize --repo-url https://github.com/username/repo-name

# Private repository
python main.py vectorize --repo-url https://github.com/username/repo-name --github-token your_token

# Custom repository name
python main.py vectorize --repo-url https://github.com/username/repo-name --repo-name my-custom-name
```

#### List Vectorized Repositories

```bash
python main.py list-repos
```

#### Get Repository Statistics

```bash
python main.py stats repo-name
```

#### Delete a Repository

```bash
python main.py delete repo-name
```

### API Server Interface

#### Start the Server

```bash
# Development mode (auto-reload)
make server-dev

# Production mode
make server
```

#### API Endpoints

- **POST** `/api/vectorize` - Start vectorizing a repository
- **GET** `/api/job/{job_id}` - Get job status and progress
- **POST** `/api/search` - Search for code using semantic similarity
- **GET** `/api/user/{username}/repos` - Get user's repositories
- **DELETE** `/api/user/{username}/repo/{repo_name}` - Delete repository
- **GET** `/api/health` - Health check

#### Example API Usage

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
results = requests.post("http://localhost:8000/api/search", json={
    "query": "authentication function",
    "username": "john_doe"
}).json()
```

#### Interactive API Documentation

Visit `http://localhost:8000/docs` for interactive Swagger documentation.

## Database Schema

### Tables

1. **repositories**: Stores repository metadata
   - `id`: Primary key
   - `repo_name`: Repository name
   - `repo_url`: Repository URL
   - `clone_path`: Local clone path
   - `status`: Processing status (pending, processing, completed, failed)
   - `created_at`, `updated_at`: Timestamps

2. **code_files**: Stores information about code files
   - `id`: Primary key
   - `repository_id`: Foreign key to repositories
   - `file_path`: Relative file path
   - `file_name`: File name
   - `file_extension`: File extension
   - `file_size`: File size in bytes
   - `content_hash`: SHA256 hash of file content

3. **code_chunks**: Stores code chunks with embeddings
   - `id`: Primary key
   - `file_id`: Foreign key to code_files
   - `chunk_index`: Chunk index within file
   - `content`: Text content
   - `start_line`, `end_line`: Line numbers
   - `token_count`: Number of tokens
   - `embedding`: Vector embedding (1536 dimensions)
   - `created_at`: Timestamp

### Indexes

- Vector similarity index on `code_chunks.embedding` using IVFFlat
- Indexes on foreign keys and frequently queried columns

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://vectorize_user:vectorize_password@localhost:5432/vectorize_db` |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | OpenAI embedding model | `text-embedding-ada-002` |
| `GITHUB_TOKEN` | GitHub token for private repos | Optional |
| `GITHUB_USERNAME` | GitHub username | Optional |
| `CHUNK_SIZE` | Maximum tokens per chunk | `1000` |
| `CHUNK_OVERLAP` | Token overlap between chunks | `200` |
| `MAX_FILE_SIZE` | Maximum file size in bytes | `1048576` (1MB) |

### Supported File Extensions

The tool supports a wide range of programming languages and file types:

- **Programming Languages**: Python, JavaScript, TypeScript, Java, C++, C#, PHP, Ruby, Go, Rust, Swift, Kotlin, Scala, Clojure, Haskell, ML, F#, R, MATLAB
- **Web Technologies**: HTML, CSS, SCSS, SASS, Vue, Svelte, Astro
- **Configuration**: YAML, JSON, XML, TOML, INI, CFG
- **Documentation**: Markdown, RST, TeX
- **Shell Scripts**: Bash, Zsh, Fish, PowerShell
- **Others**: SQL, Vim, Lisp, Emacs Lisp

## API Integration

The vectorized code can be used with LLMs for:

- **Code Search**: Find relevant code snippets using semantic similarity
- **Code Generation**: Use code context for better code generation
- **Documentation**: Generate documentation from code
- **Refactoring**: Identify similar code patterns
- **Bug Detection**: Find similar bug patterns

### Example Query

```sql
-- Find similar code chunks
SELECT 
    cc.content,
    cf.file_path,
    cc.start_line,
    cc.end_line,
    1 - (cc.embedding <=> '[query_embedding]') as similarity
FROM code_chunks cc
JOIN code_files cf ON cc.file_id = cf.id
WHERE 1 - (cc.embedding <=> '[query_embedding]') > 0.8
ORDER BY similarity DESC
LIMIT 10;
```

## Development

### Project Structure

```
VectoriseCodeBase/
├── docker-compose.yml      # Complete stack (DB + API)
├── Dockerfile             # API container
├── start.sh              # One-command startup script
├── init.sql              # Database initialization
├── requirements.txt      # Python dependencies
├── config.py             # Configuration management
├── database.py           # Database models and connection
├── git_manager.py        # Git repository management
├── file_processor.py     # File discovery and processing
├── embedding_service.py  # OpenAI embedding service
├── vectorizer.py         # Main vectorization logic
├── server.py             # FastAPI server (main API)
├── main.py               # CLI application (optional)
├── search.py             # Semantic search utility (optional)
├── client_example.py     # API client example (optional)
├── test_setup.py         # Setup verification (optional)
├── Makefile              # Easy commands
├── env.example           # Environment template
├── API_DOCUMENTATION.md  # API documentation
├── PRODUCT_GUIDE.md      # Business/product guide
└── README.md             # This file
```

### Adding New Features

1. **New File Types**: Add extensions to `Config.SUPPORTED_EXTENSIONS`
2. **Custom Chunking**: Modify `FileProcessor.chunk_text()`
3. **Different Embeddings**: Extend `EmbeddingService` for other providers
4. **Additional Metadata**: Add columns to database models

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Ensure Docker containers are running: `docker-compose ps`
   - Check database logs: `docker-compose logs postgres`

2. **OpenAI API Error**
   - Verify API key is correct
   - Check API quota and billing

3. **Git Clone Failed**
   - For private repos, ensure GitHub token has repo access
   - Check repository URL format

4. **Memory Issues**
   - Reduce `CHUNK_SIZE` in configuration
   - Process smaller repositories first

### Logs

Enable debug logging by modifying the logging level in Python files:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs
3. Open an issue on GitHub

---

**Happy Vectorizing! 🚀** 