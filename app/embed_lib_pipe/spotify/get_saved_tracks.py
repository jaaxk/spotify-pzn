import os
import json
import subprocess
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
from tqdm import tqdm
from spotipy import Spotify

class SpotifyLibraryEncoder:
    """A class to handle Spotify library encoding and preview downloads."""
    
    def __init__(self, sp_client: Spotify, save_dir: str = "app/spotify"):
        """Initialize with a Spotify client and output directory."""
        self.sp = sp_client
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Sanitize a string to be used as a filename."""
        return "".join(c if c.isalnum() or c in " _-" else "_" for c in name)
    
    def get_saved_tracks(self) -> List[Dict[str, str]]:
        """Fetch all saved tracks from the user's library."""
        all_tracks = []
        offset = 0
        limit = 50
        total = None
        
        print("Fetching saved tracks...")
        while total is None or offset < total:
            print(f"Fetching tracks {offset} to {offset + limit}")
            results = self.sp.current_user_saved_tracks(limit=limit, offset=offset)
            total = results['total']
            
            for item in results['items']:
                track = item['track']
                all_tracks.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'preview_url': track.get('preview_url')
                })
            offset += limit
            
        return all_tracks
    
    @staticmethod
    def download_preview(url: str, filename: str) -> bool:
        """Download a preview MP3 from a URL."""
        try:
            response = requests.get(url, stream=True, timeout=10)
            if response.status_code == 200:
                with open(filename, "wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                return True
            return False
        except Exception as e:
            print(f"Error downloading preview: {e}")
            return False
    
    def process_library(self) -> Dict[str, Any]:
        """Process the user's library and download previews."""
        # Get all saved tracks
        tracks = self.get_saved_tracks()
        
        # Save tracks to JSON
        tracks_file = self.save_dir / "tracks.json"
        with open(tracks_file, "w") as f:
            json.dump(tracks, f, indent=2)
        
        # Run Node.js script to get preview URLs
        try:
            script_dir = Path(__file__).parent
            subprocess.run(
                ["node", "get_previews.js"], 
                cwd=script_dir,
                check=True
            )
        except subprocess.CalledProcessError as e:
            return {
                "status": "error",
                "message": f"Failed to run preview URL script: {str(e)}",
                "tracks_processed": 0,
                "previews_downloaded": 0
            }
        
        # Read preview URLs
        previews_file = script_dir / "preview_urls.json"
        if not previews_file.exists():
            return {
                "status": "error",
                "message": "Preview URLs file not found",
                "tracks_processed": len(tracks),
                "previews_downloaded": 0
            }
        
        with open(previews_file, "r") as f:
            preview_urls = json.load(f)
        
        # Download previews
        downloaded = 0
        for track in tqdm(tracks, desc="Downloading previews"):
            key = f"{track['name']} - {track['artist']}"
            preview_url = track.get('preview_url') or preview_urls.get(key)
            
            if not preview_url:
                print(f"⚠️ No preview for {key}")
                continue
            
            filename = self.save_dir / "spotify_previews" / f"{self.sanitize_filename(key)}.mp3"
            if filename.exists():
                continue
            
            if self.download_preview(preview_url, str(filename)):
                downloaded += 1
        
        return {
            "status": "success",
            "message": f"Downloaded {downloaded} previews out of {len(tracks)} tracks",
            "tracks_processed": len(tracks),
            "previews_downloaded": downloaded
        }

def get_saved_tracks(sp_client: Spotify) -> Dict[str, Any]:
    """
    Main function to get saved tracks and download previews.
    
    Args:
        sp_client: An authenticated Spotipy client.
        
    Returns:
        Dict containing status and results of the operation.
    """
    encoder = SpotifyLibraryEncoder(sp_client)
    return encoder.process_library()

# For backward compatibility
def main():
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from dotenv import load_dotenv
    
    load_dotenv()
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope="user-library-read"
    ))
    
    result = get_saved_tracks(sp)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
