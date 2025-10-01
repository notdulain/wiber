import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Project base directory (repo root)
BASE_DIR = Path(__file__).resolve().parents[2]

# Where to store message logs per topic
DATA_DIR = os.getenv("WIBER_DATA_DIR", str(BASE_DIR / "data"))


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Kafka Settings
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    KAFKA_TOPIC: str = os.getenv("KAFKA_TOPIC", "wiber.messages")
    KAFKA_CONSUMER_GROUP: str = os.getenv("KAFKA_CONSUMER_GROUP", "wiber-consumers")
    
    # MongoDB Settings
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "wiber")
    MONGO_COLLECTION: str = os.getenv("MONGO_COLLECTION", "messages")
    
    # API Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

# Legacy compatibility
HOST = settings.API_HOST
PORT = settings.API_PORT
