from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    image_path = Column(String, nullable=True)
    platforms = Column(String, nullable=False)  # JSON array: ["twitter","instagram"]
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending|scheduled|processing|posted|partial|failed
    created_at = Column(DateTime, server_default=func.now())
    twitter_post_id = Column(String, nullable=True)
    instagram_post_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
