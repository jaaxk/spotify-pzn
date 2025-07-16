import os
import json
import subprocess
import requests
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
SCOPE = "user-library-read"
SAVE_DIR = "spotify_previews"
os.makedirs(SAVE_DIR, exist_ok=True)

def sanitize_filename(name):
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name)

def get_track_info(sp):
    all_tracks = []
    offset = 0
    limit = 50
    total = None

    print("Fetching saved tracks...")
    while total is None or offset < total:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        total = results['total']

        for item in results['items']:
            track = item['track']
            name = track['name']
            artist = track['artists'][0]['name']  # First artist
            all_tracks.append({'name': name, 'artist': artist})
        offset += limit
    return all_tracks

def download_preview(url, filename):
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

def main():
    sp = Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE
    ))

    # Step 1: Get track name + artist
    tracks = get_track_info(sp)

    # Step 2: Write to JSON
    with open("tracks.json", "w") as f:
        json.dump(tracks, f, indent=2)

    # Step 3: Run Node.js script
    subprocess.run(["node", "get_previews.js"], check=True)

    # Step 4: Read preview URLs
    with open("preview_urls.json", "r") as f:
        preview_urls = json.load(f)

    # Step 5: Download MP3 previews
    for track in tqdm(tracks, desc="Downloading previews"):
        key = f"{track['name']} - {track['artist']}"
        preview_url = preview_urls.get(key)

        if not preview_url:
            print(f"⚠️ No preview for {key}")
            continue

        filename = os.path.join(SAVE_DIR, sanitize_filename(key) + ".mp3")
        if os.path.exists(filename):
            continue

        success = download_preview(preview_url, filename)
        if not success:
            print(f"❌ Failed to download: {key}")

    print("✅ All previews downloaded.")

if __name__ == "__main__":
    main()
