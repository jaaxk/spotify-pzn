from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import UnexpectedResponse, ApiException
import numpy as np
import os
import time
import logging
from typing import List, Dict, Any, Optional, Union, Tuple, Type, Callable
import uuid

logger = logging.getLogger(__name__)

class QdrantVectorStore:
    def __init__(self, collection_name: str = "track_embeddings", recreate_collection: bool = False):
        """
        Initialize Qdrant vector store with retry logic and connection handling.
        
        Args:
            collection_name: Name of the collection to store vectors in
            recreate_collection: If True, will delete and recreate the collection if it exists
        """
        self.collection_name = collection_name
        self.vector_size = 1024  # Size of MERT embeddings
        self.max_retries = 3
        self.retry_delay = 1.0  # Initial delay in seconds
        
        # Initialize client with retry
        self.client = self._create_client()
        
        # Initialize collection with retry
        self._init_collection(recreate_collection)
    
    def _create_client(self) -> QdrantClient:
        """Create Qdrant client with retry logic"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                client = QdrantClient(
                    url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
                    prefer_grpc=False,
                    timeout=10.0  # 10 second timeout
                )
                # Test connection
                client.get_collections()
                logger.info(f"Successfully connected to Qdrant at {client._client._client._base_url}")
                return client
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Failed to connect to Qdrant (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time:.1f}s... Error: {str(e)}"
                    )
                    time.sleep(wait_time)
        
        logger.error(f"Failed to connect to Qdrant after {self.max_retries} attempts")
        raise RuntimeError(f"Failed to connect to Qdrant: {str(last_error)}")
    
    def _init_collection(self, recreate_collection: bool) -> None:
        """Initialize collection with retry logic"""
        def operation() -> bool:
            try:
                collections = self.client.get_collections().collections
                collection_names = [collection.name for collection in collections]
                
                if recreate_collection and self.collection_name in collection_names:
                    self.client.delete_collection(collection_name=self.collection_name)
                    collection_names.remove(self.collection_name)
                
                if self.collection_name not in collection_names:
                    self._create_collection()
                
                return True
            except Exception as e:
                logger.error(f"Collection operation failed: {str(e)}")
                raise
        
        self._execute_with_retry(operation, "Failed to initialize collection")
    
    def _execute_with_retry(self, operation: Callable, error_msg: str, *args, **kwargs):
        """Execute an operation with retry logic"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except (UnexpectedResponse, ApiException, ConnectionError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"{error_msg} (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time:.1f}s... Error: {str(e)}"
                    )
                    time.sleep(wait_time)
                    # Recreate client if connection was lost
                    if isinstance(e, (ConnectionError, ApiException)):
                        self.client = self._create_client()
                else:
                    logger.error(f"{error_msg} after {self.max_retries} attempts")
                    raise RuntimeError(f"{error_msg}: {str(last_error)}") from last_error
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                raise
    
    def _create_collection(self):
        """Create a new collection with the specified parameters"""
        def operation():
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
        self._execute_with_retry(operation, "Failed to create collection")
    
    def store_embedding(
        self, 
        track_id: str, 
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store an embedding in the vector store with retry logic.
        
        Args:
            track_id: Unique identifier for the track
            embedding: The embedding vector to store (numpy array or list)
            metadata: Optional metadata to store with the embedding
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not isinstance(embedding, (list, np.ndarray)):
            raise ValueError("Embedding must be a list or numpy array")
            
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
            
        if len(embedding) != self.vector_size:
            raise ValueError(f"Embedding size must be {self.vector_size}, got {len(embedding)}")
        
        def operation():
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=track_id,
                        vector=embedding,
                        payload=metadata or {}
                    )
                ]
            )
        
        try:
            self._execute_with_retry(operation, f"Failed to store embedding for track {track_id}")
            logger.info(f"Successfully stored embedding for track {track_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing embedding for track {track_id}: {str(e)}")
            return False
    
    def get_similar_tracks(
        self, 
        embedding: Union[np.ndarray, List[float]],
        limit: int = 10,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find tracks similar to the given embedding with retry logic.
        
        Args:
            embedding: The query embedding (numpy array or list)
            limit: Maximum number of results to return
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of similar tracks with scores and metadata
        """
        # Convert numpy array to list if needed
        if isinstance(embedding, np.ndarray):
            query_vector = embedding.tolist()
        else:
            query_vector = embedding
        
        def operation():
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=min_score
            )
        
        try:
            search_results = self._execute_with_retry(
                operation, 
                f"Failed to find similar tracks (limit={limit}, min_score={min_score})"
            )
            
            # Format results
            results = []
            for hit in search_results:
                results.append({
                    "track_id": hit.id,
                    "score": hit.score,
                    **hit.payload
                })
            
            logger.debug(f"Found {len(results)} similar tracks")
            return results
            
        except Exception as e:
            logger.error(f"Error finding similar tracks: {str(e)}")
            return []
    
    def get_embedding(self, track_id: str) -> Optional[np.ndarray]:
        """
        Retrieve an embedding from the vector store with retry logic.
        
        Args:
            track_id: The track ID to retrieve
            
        Returns:
            The embedding vector as a numpy array if found, None otherwise
        """
        def operation():
            return self.client.retrieve(
                collection_name=self.collection_name,
                ids=[track_id],
                with_vectors=True
            )
        
        try:
            result = self._execute_with_retry(
                operation,
                f"Failed to retrieve embedding for track {track_id}"
            )
            
            if not result:
                logger.debug(f"No embedding found for track {track_id}")
                return None
                
            return np.array(result[0].vector)
            
        except Exception as e:
            logger.error(f"Error retrieving embedding for track {track_id}: {str(e)}")
            return None
    
    def track_has_embedding(self, track_id: str) -> bool:
        """
        Check if a track already has an embedding in the vector store with retry logic.
        
        Args:
            track_id: The track ID to check
            
        Returns:
            bool: True if the track has an embedding, False otherwise
        """
        def operation():
            return self.client.retrieve(
                collection_name=self.collection_name,
                ids=[track_id],
                with_vectors=False
            )
        
        try:
            result = self._execute_with_retry(
                operation,
                f"Failed to check if track {track_id} has embedding"
            )
            return len(result) > 0
        except Exception as e:
            logger.error(f"Error checking if track {track_id} has embedding: {str(e)}")
            return False
    
    def delete_embedding(self, track_id: str) -> bool:
        """
        Delete an embedding from the vector store with retry logic.
        
        Args:
            track_id: The track ID to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        def operation():
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[track_id]
                )
            )
        
        try:
            self._execute_with_retry(
                operation,
                f"Failed to delete embedding for track {track_id}"
            )
            logger.info(f"Successfully deleted embedding for track {track_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting embedding for track {track_id}: {str(e)}")
            return False
