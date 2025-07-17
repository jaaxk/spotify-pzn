from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from .session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, spotify_id={self.spotify_id}, email={self.email})>"

class Track(Base):
    __tablename__ = "tracks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(512), nullable=False)
    artist = Column(String(512), nullable=True)
    album = Column(String(512), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    preview_url = Column(Text, nullable=True)
    has_embedding = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Track(id={self.id}, name='{self.name}', artist='{self.artist}')>"

class UserTrack(Base):
    __tablename__ = "user_tracks"
    
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        primary_key=True
    )
    track_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tracks.id", ondelete="CASCADE"), 
        primary_key=True
    )
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    play_count = Column(Integer, default=0, nullable=False)
    is_favorite = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<UserTrack(user_id={self.user_id}, track_id={self.track_id})>"

# Create all tables when this module is imported
def init_db():
    from .session import engine
    Base.metadata.create_all(bind=engine)
