"""Authentication module for Spotify OAuth."""

from .spotify import (
    get_spotify_oauth,
    get_spotify_client,
    get_spotify_auth_url
)

__all__ = [
    'get_spotify_oauth',
    'get_spotify_client',
    'get_spotify_auth_url'
]