import os
import time
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import spotipy
from spotipy.cache_handler import CacheFileHandler

def get_spotify_oauth():
    """Create and return a SpotifyOAuth instance with current config."""
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:5001/callback")
    
    # Ensure we have a cache directory
    cache_dir = ".cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, ".spotify-token-cache")
    cache_handler = CacheFileHandler(cache_path=cache_path)
    
    print(f"Creating SpotifyOAuth with:")
    print(f"  - Client ID: {client_id[:5]}...{client_id[-3:] if client_id else 'None'}")
    print(f"  - Redirect URI: {redirect_uri}")
    print(f"  - Cache path: {cache_path}")
    
    if not client_id or not client_secret:
        print("ERROR: Missing Spotify client ID or secret")
    
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="user-library-read user-read-email",
        show_dialog=True,
        cache_handler=cache_handler
    )


def is_token_expired(token_info):
    """Check if token is expired."""
    if not token_info:
        return True
    now = int(time.time())
    return token_info.get('expires_at', 0) - now < 60  # 60 seconds buffer

def refresh_token_if_needed(token_info):
    """Refresh the token if it's expired."""
    if not is_token_expired(token_info):
        return token_info
        
    sp_oauth = get_spotify_oauth()
    return sp_oauth.refresh_access_token(token_info['refresh_token'])

def get_spotify_client(token_info=None):
    """
    Get a Spotify client with the provided token info.
    
    Args:
        token_info: Token info dict containing 'access_token' and 'refresh_token'.
                   If None, will attempt to create a client with just client credentials.
    """
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("ERROR: Missing Spotify client ID or secret in environment")
        return None, None
    
    # If we have token info, try to use it
    if token_info:
        try:
            # Refresh token if needed
            if is_token_expired(token_info):
                print("Token expired, refreshing...")
                token_info = refresh_token_if_needed(token_info)
                
            # Create client with the token
            sp = spotipy.Spotify(auth=token_info['access_token'])
            return sp, token_info
        except Exception as e:
            print(f"Error creating Spotify client with token: {str(e)}")
    
    # Fall back to client credentials if no token provided or token is invalid
    try:
        print("Falling back to client credentials flow")
        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        return spotipy.Spotify(auth_manager=auth_manager), None
    except Exception as e:
        print(f"Error creating Spotify client with client credentials: {str(e)}")
        return None, None

def get_spotify_auth_url():
    """Get the Spotify authorization URL."""
    try:
        sp_oauth = get_spotify_oauth()
        auth_url = sp_oauth.get_authorize_url()
        print(f"Generated auth URL: {auth_url}")
        return auth_url
    except Exception as e:
        print(f"Error generating auth URL: {str(e)}")
        raise