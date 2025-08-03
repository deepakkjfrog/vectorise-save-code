import openai
import numpy as np
from typing import List, Dict, Optional
from config import Config
import logging
import time

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or Config.OPENAI_API_KEY
        self.model = model or Config.OPENAI_MODEL
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Create OpenAI client without setting global api_key
        self.client = openai.OpenAI(api_key=self.api_key)
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for a single text"""
        try:
            # Clean and prepare text
            text = text.strip()
            if not text:
                return None
            
            # Truncate if too long (OpenAI has limits)
            max_tokens = 8191  # OpenAI's limit for text-embedding-ada-002
            if len(text) > max_tokens * 4:  # Rough estimate: 4 chars per token
                text = text[:max_tokens * 4]
            
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None
    
    def get_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[Optional[List[float]]]:
        """Get embeddings for multiple texts in batches"""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Processing embedding batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            
            try:
                # Clean and prepare batch
                cleaned_batch = []
                for text in batch:
                    text = text.strip()
                    if text:
                        # Truncate if too long
                        max_tokens = 8191
                        if len(text) > max_tokens * 4:
                            text = text[:max_tokens * 4]
                        cleaned_batch.append(text)
                    else:
                        cleaned_batch.append("")
                
                if not any(cleaned_batch):
                    embeddings.extend([None] * len(batch))
                    continue
                
                response = self.client.embeddings.create(
                    model=self.model,
                    input=cleaned_batch
                )
                
                # Map embeddings back to original order
                batch_embeddings = []
                response_index = 0
                
                for text in cleaned_batch:
                    if text:
                        batch_embeddings.append(response.data[response_index].embedding)
                        response_index += 1
                    else:
                        batch_embeddings.append(None)
                
                embeddings.extend(batch_embeddings)
                
                # Rate limiting - be nice to OpenAI
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing embedding batch: {e}")
                embeddings.extend([None] * len(batch))
        
        return embeddings
    
    def process_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Process chunks and add embeddings"""
        if not chunks:
            return []
        
        # Extract texts for embedding
        texts = [chunk['content'] for chunk in chunks]
        
        # Get embeddings
        embeddings = self.get_embeddings_batch(texts)
        
        # Add embeddings to chunks
        processed_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            if embedding is not None:
                chunk_copy = chunk.copy()
                chunk_copy['embedding'] = embedding
                processed_chunks.append(chunk_copy)
            else:
                logger.warning(f"Failed to get embedding for chunk: {chunk.get('file_path', 'unknown')}")
        
        logger.info(f"Successfully processed {len(processed_chunks)}/{len(chunks)} chunks with embeddings")
        return processed_chunks
    
    def test_connection(self) -> bool:
        """Test OpenAI API connection"""
        try:
            test_embedding = self.get_embedding("test")
            return test_embedding is not None
        except Exception as e:
            logger.error(f"OpenAI API connection test failed: {e}")
            return False 