from flask import Flask, jsonify, request, session, redirect, url_for, render_template
import os
import sys
import json
import time
from datetime import datetime, timedelta
from celery import Celery
from dotenv import load_dotenv
import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from celery.result import AsyncResult

# Import our auth module
from app.auth.spotify import get_spotify_oauth, get_spotify_client, is_token_expired, refresh_token_if_needed, get_spotify_auth_url
from app.embed_lib_pipe.spotify.get_saved_tracks import SpotifyLibraryEncoder

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get the base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'app', 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'app', 'static')

# Create the Flask app with template and static folders
app = Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR
)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key-here")
app.config['SESSION_COOKIE_NAME'] = 'SpotifyLibraryEncoder'
app.config['SESSION_TYPE'] = 'filesystem'

# Print debug info
print(f"Base directory: {BASE_DIR}")
print(f"Template directory: {TEMPLATE_DIR}")
print(f"Static directory: {STATIC_DIR}")
print(f"Templates exist: {os.path.exists(TEMPLATE_DIR)}")
print(f"Template files: {os.listdir(TEMPLATE_DIR) if os.path.exists(TEMPLATE_DIR) else 'No templates dir'}")

# Get Redis URL from environment or use default
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')

# Configure Celery
celery = Celery(
    app.import_name,
    broker=redis_url,
    backend=redis_url
)

# Update Celery config
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60  # 25 minutes
)

class ContextTask(celery.Task):
    def __call__(self, *args, **kwargs):
        with app.app_context():
            return self.run(*args, **kwargs)

celery.Task = ContextTask
app.celery = celery

# Initialize the Spotify OAuth client (lazy loaded when needed)

@app.route('/')
def index():
    #if not session.get('token_info'):
    auth_url = get_spotify_auth_url()
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:5001/callback")
    error = request.args.get('error')
    print(f"Rendering login page with auth URL: {auth_url}")
    return render_template('login.html', 
                        auth_url=auth_url,
                        redirect_uri=redirect_uri,
                        error=error)
    #return redirect('/callback')

@app.route('/callback')
def callback():
    try:
        # Debug log all request arguments
        print(f"Callback received with args: {request.args}")
        
        # Handle Spotify OAuth callback
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            print(f"Spotify OAuth error: {error}")
            return redirect(f'/?error=spotify_{error}')
            
        if not code:
            print("No code parameter in callback")
            return redirect('/?error=no_code')
            
        try:
            # Get access token and store in session
            sp_oauth = get_spotify_oauth()
            token_info = sp_oauth.get_access_token(code)
            
            if not token_info:
                return redirect('/?error=token_failed')
                
            # Ensure we have all required token info
            if 'access_token' not in token_info:
                return redirect('/?error=invalid_token_response')
                
            # Store token info in session
            session['token_info'] = token_info
            
            # Create a client with the token
            sp = spotipy.Spotify(auth=token_info['access_token'])
            
            # Get user info
            user_info = sp.current_user()
            if not user_info or 'id' not in user_info:
                return redirect('/?error=user_info_failed')
                
            user_id = user_info['id']
            session['user_id'] = user_id
            
            # Store the refresh token if we got one
            if 'refresh_token' in token_info:
                session['refresh_token'] = token_info['refresh_token']
            
            # Redirect to the main app page
            return render_template('callback.html', 
                                user_id=user_id,
                                display_name=user_info.get('display_name', 'User'))
                                
        except spotipy.SpotifyException as e:
            print(f"Spotify API error: {str(e)}")
            return redirect('/?error=spotify_api_error')
            
    except Exception as e:
        error_msg = str(e).replace('\n', ' ').replace('\r', ' ')[:200]  # Sanitize error message
        print(f"Error in callback: {error_msg}")
        return redirect(f'/?error=callback_error')

@app.route('/api/encode-library', methods=['POST'])
def encode_library():
    if 'user_id' not in session or 'token_info' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401

    token_info = session['token_info']
    sp, updated_token_info = get_spotify_client(token_info.copy())

    if not sp:
        return jsonify({'status': 'error', 'message': 'Spotify auth failed'}), 401

    # Refresh token if needed
    if updated_token_info:
        session['token_info'] = updated_token_info
        token_info = updated_token_info

    try:
        # Fetch user's saved tracks (here in Flask, not Celery)
        encoder = SpotifyLibraryEncoder(sp)
        print("Fetching saved tracks...")
        tracks = encoder.get_saved_tracks()
        print(f"Fetched {len(tracks)} tracks")
        if not tracks:
            return jsonify({'status': 'error', 'message': 'No saved tracks'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': f"Spotify error: {e}"}), 500

    print("Passing tracks to Celery...")
    # Pass just track metadata and user_id to Celery
    from app.embed_lib_pipe.tasks import process_library
    print("Passing tracks to Celery...")
    task = process_library.delay({
        'user_id': session['user_id'],
        'tracks': tracks
    })

    return jsonify({'status': 'started', 'task_id': task.id})


@app.route('/api/task-status/<task_id>')
def task_status(task_id):
    try:
        from app.embed_lib_pipe.tasks import get_task_status
        result = get_task_status(task_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# Health check endpoint
@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'spotify-pzn',
        'version': '1.0.0'
    })

# Serve static files
@app.route('/static/<path:path>')
def serve_static(path):
    return app.send_static_file(path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n=== Starting Flask app on port {port} ===\n")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Files in current directory: {os.listdir('.')}")
    print(f"App root path: {app.root_path}")
    print(f"Template folder: {app.template_folder}")
    print(f"Static folder: {app.static_folder}")
    
    app.run(host='0.0.0.0', port=port, debug=True)