from flask import Flask, redirect, request, session, url_for
from spotipy.oauth2 import SpotifyOAuth
import spotipy
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "your-secret"
app.config['SESSION_COOKIE_NAME'] = 'SpotifyPersonalizer'

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-read-recently-played user-read-playback-state"
)

@app.route('/')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/recent')

@app.route('/recent')
def recent_tracks():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    
    sp = spotipy.Spotify(auth=token_info['access_token'])
    results = sp.current_user_recently_played(limit=10)
    
    tracks = [f"{item['track']['name']} by {item['track']['artists'][0]['name']}" for item in results['items']]
    return "<br>".join(tracks)

if __name__ == '__main__':
    app.run(port=8888)