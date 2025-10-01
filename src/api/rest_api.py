"""
REST API for Wiber Messaging System

This module provides HTTP endpoints for sending and retrieving messages.
Integrates with Kafka (producer) and MongoDB (queries).
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
from contextlib import asynccontextmanager

from src.producer.producer import get_producer
from src.database.mongodb_handler import get_db
from src.config.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models for request/response
class MessageRequest(BaseModel):
    """Request model for sending a message"""
    fromUser: str = Field(..., min_length=1, max_length=50, description="Sender username")
    toUser: str = Field(..., min_length=1, max_length=50, description="Recipient username")
    content: str = Field(..., min_length=1, max_length=5000, description="Message content")
    
    class Config:
        json_schema_extra = {
            "example": {
                "fromUser": "alice",
                "toUser": "bob",
                "content": "Hello, Bob! How are you?"
            }
        }


class MessageResponse(BaseModel):
    """Response model for a message"""
    messageId: str = Field(..., description="Unique message ID")
    fromUser: str = Field(..., description="Sender username")
    toUser: str = Field(..., description="Recipient username")
    content: str = Field(..., description="Message content")
    timestamp: int = Field(..., description="Unix timestamp in milliseconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "messageId": "123e4567-e89b-12d3-a456-426614174000",
                "fromUser": "alice",
                "toUser": "bob",
                "content": "Hello, Bob! How are you?",
                "timestamp": 1696176000000
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    kafka: Optional[str] = None
    mongodb: Optional[str] = None


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    logger.info("Starting Wiber API...")
    logger.info(f"Kafka: {settings.KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"MongoDB: {settings.MONGO_URI}")
    
    # Initialize services (lazy initialization on first use)
    try:
        # Test connections
        producer = get_producer()
        db = get_db()
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Continue anyway - will fail on first request if there's an issue
    
    yield
    
    # Shutdown
    logger.info("Shutting down Wiber API...")
    try:
        producer = get_producer()
        producer.close()
        db = get_db()
        db.close()
        logger.info("Services closed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Wiber Messaging API",
    description="A distributed messaging system built with Kafka and MongoDB",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Endpoints

@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Wiber Messaging API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.post("/messages", response_model=MessageResponse, tags=["Messages"])
async def send_message(request: MessageRequest):
    """
    Send a message via Kafka
    
    The message is published to Kafka and will be asynchronously
    processed by the consumer service and stored in MongoDB.
    
    - **fromUser**: Username of the sender
    - **toUser**: Username of the recipient
    - **content**: Message content
    """
    try:
        producer = get_producer()
        
        # Send message to Kafka
        message = producer.send_message(
            from_user=request.fromUser,
            to_user=request.toUser,
            content=request.content
        )
        
        logger.info(f"Message sent: {message['messageId']} from {request.fromUser} to {request.toUser}")
        
        return MessageResponse(**message)
        
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send message: {str(e)}"
        )


@app.get("/messages/{user1}/{user2}", response_model=List[MessageResponse], tags=["Messages"])
async def get_messages(
    user1: str,
    user2: str,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum messages to return"),
    skip: int = Query(default=0, ge=0, description="Number of messages to skip (pagination)")
):
    """
    Get messages between two users
    
    Returns messages in chronological order (oldest first).
    
    - **user1**: First username
    - **user2**: Second username
    - **limit**: Maximum number of messages (default: 50, max: 500)
    - **skip**: Number of messages to skip for pagination (default: 0)
    """
    try:
        db = get_db()
        
        # Retrieve messages from MongoDB
        messages = db.get_messages(user1, user2, limit=limit, skip=skip)
        
        logger.info(f"Retrieved {len(messages)} messages between {user1} and {user2}")
        
        return [MessageResponse(**msg) for msg in messages]
        
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve messages: {str(e)}"
        )


@app.get("/messages/user/{username}", response_model=List[MessageResponse], tags=["Messages"])
async def get_user_messages(
    username: str,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum messages to return")
):
    """
    Get recent messages for a user (sent or received)
    
    Returns most recent messages first.
    
    - **username**: Username to get messages for
    - **limit**: Maximum number of messages (default: 100, max: 500)
    """
    try:
        db = get_db()
        
        # Retrieve recent messages
        messages = db.get_recent_messages(username, limit=limit)
        
        logger.info(f"Retrieved {len(messages)} recent messages for {username}")
        
        return [MessageResponse(**msg) for msg in messages]
        
    except Exception as e:
        logger.error(f"Error retrieving user messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user messages: {str(e)}"
        )


@app.get("/messages/count", tags=["Messages"])
async def count_messages(
    user1: Optional[str] = Query(None, description="First user (optional)"),
    user2: Optional[str] = Query(None, description="Second user (optional)")
):
    """
    Count messages
    
    - No parameters: Total message count
    - user1 only: Count for that user
    - user1 and user2: Count between those users
    """
    try:
        db = get_db()
        count = db.count_messages(user1, user2)
        
        return {
            "count": count,
            "user1": user1,
            "user2": user2
        }
        
    except Exception as e:
        logger.error(f"Error counting messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to count messages: {str(e)}"
        )


# Health Check Endpoints

@app.get("/health/liveness", response_model=HealthResponse, tags=["Health"])
async def liveness():
    """
    Liveness probe - checks if the service is running
    
    Used by Docker/Kubernetes to detect if the container is alive.
    """
    return HealthResponse(status="alive")


@app.get("/health/readiness", response_model=HealthResponse, tags=["Health"])
async def readiness():
    """
    Readiness probe - checks if the service is ready to handle requests
    
    Verifies connections to Kafka and MongoDB.
    Used by Docker/Kubernetes to detect if the container is ready.
    """
    kafka_status = "unknown"
    mongodb_status = "unknown"
    
    try:
        # Check Kafka connection
        try:
            producer = get_producer()
            if producer.producer.bootstrap_connected():
                kafka_status = "connected"
            else:
                kafka_status = "disconnected"
        except Exception as e:
            kafka_status = f"error: {str(e)}"
        
        # Check MongoDB connection
        try:
            db = get_db()
            if db.health_check():
                mongodb_status = "connected"
            else:
                mongodb_status = "disconnected"
        except Exception as e:
            mongodb_status = f"error: {str(e)}"
        
        # Service is ready only if both dependencies are available
        if kafka_status == "connected" and mongodb_status == "connected":
            return HealthResponse(
                status="ready",
                kafka=kafka_status,
                mongodb=mongodb_status
            )
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not ready",
                    "kafka": kafka_status,
                    "mongodb": mongodb_status
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Health check failed: {str(e)}"
        )


# Run with: uvicorn src.api.rest_api:app --host 0.0.0.0 --port 8000 --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.rest_api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info"
    )

