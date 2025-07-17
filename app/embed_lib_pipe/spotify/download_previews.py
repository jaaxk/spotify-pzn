import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
from tqdm import tqdm
import os

class PreviewDownloader:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.base_dir = Path(__file__).parent / "data"
        self.previews_dir = self.base_dir / "mp3"
        self.previews_dir.mkdir(parents=True, exist_ok=True)
        
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to be filesystem-safe."""
        return "".join(c if c.isalnum() or c in ' -_' else '_' for c in filename)
    
    def download_preview(self, url: str, filepath: str) -> bool:
        """Download a single preview file."""
        try:
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            print(f"Error downloading {url}: {str(e)}")
            return False
    
    def get_preview_urls(self, tracks: List[Dict[str, Any]]) -> Dict[str, str]:
        """Get preview URLs using Node.js script."""
        script_dir = Path(__file__).parent
        tracks_file = self.base_dir / "tracks.json"
        previews_file = self.base_dir / "preview_urls.json"
        
        # Clean up any existing files
        if previews_file.exists():
            previews_file.unlink()
            
        # Prepare tracks data with required fields
        tracks_data = []
        for track in tracks:
            track_data = {
                'name': track.get('name', ''),
                'artist': track.get('artist', '')
            }
            tracks_data.append(track_data)
        
        # Save tracks to JSON for Node.js script
        with open(tracks_file, "w") as f:
            json.dump(tracks_data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved tracks data to {tracks_file}")
        print(f"Running Node.js script from {script_dir}")
        
        try:
            # Create package.json if it doesn't exist
            package_json = script_dir / "package.json"
            if not package_json.exists():
                with open(package_json, "w") as f:
                    json.dump({
                        "name": "spotify-preview-downloader",
                        "version": "1.0.0",
                        "description": "Download Spotify previews",
                        "main": "get_previews.js",
                        "dependencies": {
                            "spotify-preview-finder": "^1.0.0",
                            "dotenv": "^16.0.0"
                        }
                    }, f, indent=2)
            
            # Install required Node.js dependencies
            print("Installing Node.js dependencies...")
            install_result = subprocess.run(
                ["npm", "install"],
                cwd=script_dir,
                capture_output=True,
                text=True
            )
            
            print(f"npm install output:\n{install_result.stdout}")
            if install_result.stderr:
                print(f"npm install errors:\n{install_result.stderr}")
            
            # Get Spotify credentials from environment
            spotify_creds = {
                'SPOTIFY_CLIENT_ID': os.getenv('SPOTIPY_CLIENT_ID'),
                'SPOTIFY_CLIENT_SECRET': os.getenv('SPOTIPY_CLIENT_SECRET')
            }
            
            if not all(spotify_creds.values()):
                raise ValueError("Missing Spotify credentials in environment variables")
            
            # Run the Node.js script with environment variables
            print("Running preview finder script...")
            env = os.environ.copy()
            env.update({
                'SPOTIFY_CLIENT_ID': spotify_creds['SPOTIFY_CLIENT_ID'],
                'SPOTIFY_CLIENT_SECRET': spotify_creds['SPOTIFY_CLIENT_SECRET']
            })
            
            result = subprocess.run(
                ["node", "get_previews.js"],
                cwd=script_dir,
                capture_output=True,
                text=True,
                env=env  # Pass the environment variables to the subprocess
            )
            
            print(f"Node.js script output:\n{result.stdout}")
            if result.stderr:
                print(f"Node.js script errors:\n{result.stderr}")
            
            # Read preview URLs
            if previews_file.exists():
                with open(previews_file, "r") as f:
                    return json.load(f)
            else:
                print(f"Warning: {previews_file} not found after script execution")
                
        except subprocess.CalledProcessError as e:
            print(f"Error running preview URL script (exit code {e.returncode}):")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return {}
    
    def download_all_previews(self, tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Download all previews for the given tracks."""
        # Get preview URLs using Node.js script
        preview_urls = self.get_preview_urls(tracks)
        
        # Download previews
        downloaded = 0
        for track in tqdm(tracks, desc="Downloading previews"):
            key = f"{track['name']} - {track['artist']}"
            preview_url = track.get('preview_url') or preview_urls.get(key)
            
            if not preview_url:
                print(f"⚠️ No preview for {key}")
                continue
            
            filename = self.previews_dir / f"{self.sanitize_filename(key)}.mp3"
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
