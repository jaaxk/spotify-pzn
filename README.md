# 🎧 Context-Aware Spotify Music Personalizer

A smart, context-aware music recommendation system built on the Spotify API. This app learns an individual user's music preferences based on contextual data like **time of day**, **location**, and **user activity** (e.g., "at the gym", "studying"), and aims to recommend music accordingly.

Built with:
- Python
- Flask (web interface)
- Spotipy (Spotify API wrapper)
- NLP for activity classification
- Transformer-based audio and text embeddings (planned in later sprints)
- SQLite / local storage for prototyping

---

## 🚀 Features (Current & Planned)

### ✅ MVP Features
- User authentication via Spotify OAuth
- Collect recent listening history from Spotify
- Capture real-time contextual data:
  - Time and date
  - Location (via IP-based geolocation)
  - User activity (free-text input)
- Store listening + context logs for ML

### 🔜 Future Additions
- NLP model to classify user activities into categories
- Personalized recommendation engine (based on context + audio features)
- Audio and lyrics embedding models (e.g., MusicCLIP, T5)
- Nearest-neighbor recommendation from Spotify's catalog
- Dynamic playlists based on user’s current context
- Mobile version via React Native or Flutter frontend
- “No-input” prediction of activity (based on time, location, playback habits)

---
