-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create tables for storing codebase information
CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    repo_name VARCHAR(255) NOT NULL,
    repo_url VARCHAR(500) NOT NULL,
    clone_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS code_files (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    file_path VARCHAR(500) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_extension VARCHAR(50),
    file_size INTEGER,
    content_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS code_chunks (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES code_files(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    token_count INTEGER,
    embedding vector(1536), -- OpenAI embedding dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_repositories_repo_name ON repositories(repo_name);
CREATE INDEX IF NOT EXISTS idx_code_files_repository_id ON code_files(repository_id);
CREATE INDEX IF NOT EXISTS idx_code_files_file_path ON code_files(file_path);
CREATE INDEX IF NOT EXISTS idx_code_chunks_file_id ON code_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_code_chunks_embedding ON code_chunks USING ivfflat (embedding vector_cosine_ops);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for repositories table
CREATE TRIGGER update_repositories_updated_at 
    BEFORE UPDATE ON repositories 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); 