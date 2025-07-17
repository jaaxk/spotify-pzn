import os
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from celery import Celery
from celery.signals import after_setup_task_logger, after_setup_logger

# Import our pipeline steps with absolute imports to avoid any circular imports
from app.embed_lib_pipe.steps.convert import convert_directory
from app.embed_lib_pipe.models.mert import MERTWrapper

# Set up Celery with explicit configuration
app = Celery(
    'pipeline',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
    include=['app.embed_lib_pipe.tasks']
)

# Configure Celery to not use Flask context
app.conf.update(
    task_always_eager=False,
    task_eager_propagates=False,
    task_create_missing_queues=True,
    task_default_queue='pipeline',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60  # 25 minutes
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
# Go up three levels from current file to reach project root
BASE_DIR = Path(__file__).parent.parent.parent
PREVIEWS_DIR = BASE_DIR / "app" / "embed_lib_pipe" / "spotify" / "data" / "mp3"
WAV_DIR = BASE_DIR / "app" / "embed_lib_pipe" / "spotify" / "data" / "wav"
EMBEDDINGS_DIR = BASE_DIR / "app" / "embed_lib_pipe" / "models" / "embeddings"

# Create necessary directories
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
WAV_DIR.mkdir(parents=True, exist_ok=True)
EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

class TaskStatus:
    PENDING = 'PENDING'
    STARTED = 'STARTED'
    PROCESSING = 'PROCESSING'  # Added this line
    DOWNLOADING = 'DOWNLOADING'
    CONVERTING = 'CONVERTING'
    EMBEDDING = 'EMBEDDING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'

# Initialize MERT model wrapper
mert_wrapper = None

def get_mert_wrapper():
    """Lazy load the MERT wrapper to avoid loading the model at module level."""
    global mert_wrapper
    if mert_wrapper is None:
        mert_wrapper = MERTWrapper()
        #mert_wrapper.load()
    return mert_wrapper

@app.task(bind=True, name='process_library')
def process_library(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main task that orchestrates the entire pipeline:
    
    Args:
        task_data (dict): Dictionary containing:
            - user_id (str): The Spotify user ID
            - tracks (list): Pre-fetched list of tracks from Spotify
    """
    print("\n=== CELERY TASK STARTED ===")
    logger.info("CELERY TASK STARTED")
    print(f"Task ID: {self.request.id}")
    print(f"User ID: {task_data.get('user_id')}")
    print(f"Number of tracks: {len(task_data.get('tracks', []))}")
    print("=== CELERY TASK PROCESSING ===\n")
    
    user_id = task_data.get('user_id')
    tracks = task_data.get('tracks', [])
    
    logger.info(f"Starting library processing for user: {user_id}")
    logger.info(f"Received {len(tracks)} tracks to process")
    
    if not tracks:
        error_msg = "No tracks provided for processing"
        logger.error(error_msg)
        self.update_state(
            state=TaskStatus.FAILED,
            meta={'status': error_msg}
        )
        return {
            'status': 'error',
            'message': error_msg,
            'user_id': user_id
        }
    
    try:
        # 1. Process each track
        self.update_state(
            state=TaskStatus.PROCESSING,
            meta={'status': 'Processing tracks...'}
        )
        logger.info(f"Processing {len(tracks)} tracks...")
        
        # Extract relevant track information
        processed_tracks = []
        for track in tracks:
            if not isinstance(track, dict):
                logger.warning(f"Skipping invalid track: {track}")
                continue
                
            try:
                # Debug the track structure
                logger.debug(f"Processing track data: {json.dumps(track, indent=2)}")
                
                # Try different ways to get artist name
                artist_name = 'Unknown Artist'
                
                # Case 1: Direct 'artists' list
                if 'artists' in track and isinstance(track['artists'], list) and track['artists']:
                    if isinstance(track['artists'][0], dict):
                        artist_name = track['artists'][0].get('name', 'Unknown Artist')
                    elif isinstance(track['artists'][0], str):
                        artist_name = track['artists'][0]
                # Case 2: Nested 'track' object with artists
                elif 'track' in track and isinstance(track['track'], dict) and 'artists' in track['track']:
                    artists = track['track']['artists']
                    if isinstance(artists, list) and artists:
                        if isinstance(artists[0], dict):
                            artist_name = artists[0].get('name', 'Unknown Artist')
                        elif isinstance(artists[0], str):
                            artist_name = artists[0]
                # Case 3: Direct 'artist' field
                elif 'artist' in track and isinstance(track['artist'], str):
                    artist_name = track['artist']
                
                # Get track name, checking for nested 'track' object
                track_name = track.get('name', '')
                if not track_name and 'track' in track and isinstance(track['track'], dict):
                    track_name = track['track'].get('name', 'Unknown Track')
                
                track_data = {
                    'id': track.get('id', ''),
                    'name': track_name or 'Unknown Track',
                    'artist': artist_name,
                    'preview_url': track.get('preview_url', ''),
                    'duration_ms': track.get('duration_ms', 0)
                }
                
                logger.debug(f"Processed track: {track_data}")
                processed_tracks.append(track_data)
            except Exception as e:
                logger.error(f"Error processing track {track.get('id', 'unknown')}: {str(e)}")
                continue
        
        if not processed_tracks:
            error_msg = "No valid tracks found to process"
            logger.error(error_msg)
            self.update_state(
                state=TaskStatus.FAILED,
                meta={'status': error_msg}
            )
            return {
                'status': 'error',
                'message': error_msg,
                'user_id': user_id
            }
            
        logger.info(f"Successfully processed {len(processed_tracks)} tracks")
        
        # 2. Download previews
        self.update_state(
            state=TaskStatus.DOWNLOADING,
            meta={'status': 'Downloading audio previews...'}
        )
        logger.info("Downloading audio previews...")
        
        from app.embed_lib_pipe.spotify.download_previews import PreviewDownloader
        downloader = PreviewDownloader(user_id=user_id)
        download_result = downloader.download_all_previews(processed_tracks)
        
        if download_result.get('status') != 'success':
            error_msg = f"Failed to download previews: {download_result.get('message', 'Unknown error')}"
            logger.error(error_msg)
            self.update_state(
                state=TaskStatus.FAILED,
                meta={'status': error_msg}
            )
            return {
                'status': 'error',
                'message': error_msg,
                'user_id': user_id
            }
            
        logger.info(f"Successfully downloaded {download_result['previews_downloaded']} previews")
        
        # 3. Convert MP3s to WAV (if needed)
        self.update_state(
            state=TaskStatus.CONVERTING,
            meta={'status': 'Converting audio files...'}
        )
        logger.info("Converting audio files...")
        
        # Use the same directory structure as PreviewDownloader
        wav_files = convert_directory(
            input_dir=PREVIEWS_DIR,
            output_dir=WAV_DIR,
            sample_rate=24000  # MERT expects 24kHz
        )
        logger.info(f"Converted {len(wav_files)} files to WAV format")
        
        # 3. Extract embeddings
        self.update_state(
            state=TaskStatus.EMBEDDING,
            meta={'status': 'Extracting embeddings...'}
        )
        logger.info("Extracting embeddings with MERT...")
        
        mert = get_mert_wrapper()
        print('MERT LOADED')
        results = mert.process_directory(
            input_dir=WAV_DIR,
            output_file=EMBEDDINGS_DIR / f"{user_id}_embeddings.pt",
            layer=-1,  # Last layer
            reduce='mean'  # Average over time
        )
        
        # 4. Prepare results
        result = {
            'status': TaskStatus.COMPLETED,
            'message': 'Library processing completed successfully',
            'tracks_processed': len(tracks),
            'embeddings_generated': len(results),
            'embeddings_path': str(EMBEDDINGS_DIR / f"{user_id}_embeddings.pt")
        }
        
        logger.info(f"Task {self.request.id} completed successfully")
        return result
        
    except Exception as e:
        error_msg = f"Error in process_library: {str(e)}"
        logger.error(error_msg, exc_info=True)
        self.update_state(
            state=TaskStatus.FAILED,
            meta={'status': 'Failed', 'error': error_msg}
        )
        raise

@app.task
def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get the status of a task."""
    from celery.result import AsyncResult
    
    task = AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Pending...',
            'progress': 0
        }
    elif task.state == 'FAILURE':
        response = {
            'state': 'FAILURE',
            'status': str(task.info),  # Error message
            'progress': 100
        }
    elif task.state == TaskStatus.COMPLETED:
        response = {
            'state': 'COMPLETED',
            'status': 'Task completed successfully',
            'result': task.result,
            'progress': 100
        }
    else:
        # For custom states (PROCESSING, CONVERTING, EMBEDDING)
        response = {
            'state': task.state,
            'status': task.info.get('status', 'Processing...') if isinstance(task.info, dict) else str(task.info),
            'progress': _calculate_progress(task.state)
        }
    
    return response

def _calculate_progress(state: str) -> int:
    """Calculate progress percentage based on task state."""
    progress_map = {
        'PENDING': 0,
        'STARTED': 5,
        'PROCESSING': 20,  # Added this line
        'DOWNLOADING': 40,
        'CONVERTING': 60,
        'EMBEDDING': 80,
        'COMPLETED': 100,
        'FAILED': 100
    }
    return progress_map.get(state, 0)