"""
MongoDB Handler for Wiber Messaging System

This module handles all MongoDB operations with proper replication and consistency.
Responsibility: Member 2 (Replication & Consistency)
"""

from pymongo import MongoClient, ASCENDING, WriteConcern
from pymongo.errors import DuplicateKeyError, PyMongoError
import logging
from typing import List, Dict, Optional
from src.config.settings import settings

logger = logging.getLogger(__name__)


class MongoDBHandler:
    """
    MongoDB handler with replication and consistency features
    
    Features:
    - Unique message IDs (deduplication)
    - Indexed queries for fast retrieval
    - Write concern for durability
    - Ordered message retrieval
    """
    
    def __init__(self):
        """Initialize MongoDB connection and create indexes"""
        try:
            # Connect to MongoDB
            # Member 2's responsibility: Write concern for durability
            self.client = MongoClient(
                settings.MONGO_URI,
                serverSelectionTimeoutMS=5000
            )
            
            # Set write concern for durability
            # w='majority' ensures data is replicated before confirming
            # j=True ensures data is written to journal (disk)
            from pymongo.write_concern import WriteConcern
            self.write_concern = WriteConcern(w='majority', j=True)
            
            self.db = self.client[settings.MONGO_DB]
            self.collection = self.db[settings.MONGO_COLLECTION]
            
            # Test connection
            self.client.admin.command('ping')
            logger.info(f"MongoDB connected: {settings.MONGO_URI}")
            
            # Create indexes for performance and deduplication
            self._create_indexes()
            
        except PyMongoError as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def _create_indexes(self):
        """
        Create indexes for performance and consistency
        
        Member 2's responsibility: Efficient replication and deduplication
        """
        try:
            # Unique index on messageId to prevent duplicates
            # This is crucial for exactly-once semantics
            self.collection.create_index(
                [("messageId", ASCENDING)],
                unique=True,
                name="idx_messageId_unique"
            )
            logger.info("Created unique index on messageId")
            
            # Compound index for fast conversation queries
            # Sorted by timestamp for ordering (Member 3's responsibility)
            self.collection.create_index(
                [
                    ("fromUser", ASCENDING),
                    ("toUser", ASCENDING),
                    ("timestamp", ASCENDING)
                ],
                name="idx_conversation_timeline"
            )
            logger.info("Created compound index for conversation queries")
            
            # Index on timestamp for general sorting
            self.collection.create_index(
                [("timestamp", ASCENDING)],
                name="idx_timestamp"
            )
            logger.info("Created index on timestamp")
            
        except PyMongoError as e:
            logger.warning(f"Index creation warning (may already exist): {e}")
    
    def save_message(self, message_data: Dict) -> bool:
        """
        Save a message to MongoDB with deduplication
        
        Args:
            message_data: Message dictionary containing messageId, fromUser, toUser, etc.
        
        Returns:
            True if message saved successfully or already exists
        
        Raises:
            PyMongoError: If database operation fails
        """
        try:
            # Member 2's responsibility: Ensure no duplicates with write concern
            result = self.collection.with_options(
                write_concern=self.write_concern
            ).insert_one(message_data)
            logger.info(
                f"Message saved: {message_data['messageId']} "
                f"(MongoDB ID: {result.inserted_id})"
            )
            return True
            
        except DuplicateKeyError:
            # Message already exists - this is expected with at-least-once delivery
            # Member 1 & 2's responsibility: Idempotency
            logger.info(
                f"Duplicate message ignored (idempotency): {message_data['messageId']}"
            )
            return True  # Still return success - idempotent operation
            
        except PyMongoError as e:
            logger.error(f"Failed to save message {message_data.get('messageId')}: {e}")
            raise
    
    def get_messages(
        self,
        user1: str,
        user2: str,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict]:
        """
        Get messages between two users
        
        Member 3's responsibility: Maintain order by timestamp
        
        Args:
            user1: First user
            user2: Second user
            limit: Maximum number of messages to return
            skip: Number of messages to skip (pagination)
        
        Returns:
            List of message dictionaries ordered by timestamp
        """
        try:
            # Query for messages in both directions
            query = {
                "$or": [
                    {"fromUser": user1, "toUser": user2},
                    {"fromUser": user2, "toUser": user1}
                ]
            }
            
            # Projection to exclude MongoDB internal _id
            projection = {"_id": 0}
            
            # Member 3's responsibility: Sort by timestamp for correct order
            messages = self.collection.find(
                query,
                projection
            ).sort("timestamp", ASCENDING).skip(skip).limit(limit)
            
            result = list(messages)
            logger.info(f"Retrieved {len(result)} messages between {user1} and {user2}")
            return result
            
        except PyMongoError as e:
            logger.error(f"Failed to retrieve messages: {e}")
            raise
    
    def get_recent_messages(
        self,
        user: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get recent messages for a user (sent or received)
        
        Args:
            user: Username
            limit: Maximum number of messages
        
        Returns:
            List of recent messages ordered by timestamp
        """
        try:
            query = {
                "$or": [
                    {"fromUser": user},
                    {"toUser": user}
                ]
            }
            
            projection = {"_id": 0}
            
            messages = self.collection.find(
                query,
                projection
            ).sort("timestamp", -1).limit(limit)  # Descending for most recent first
            
            result = list(messages)
            logger.info(f"Retrieved {len(result)} recent messages for {user}")
            return result
            
        except PyMongoError as e:
            logger.error(f"Failed to retrieve recent messages: {e}")
            raise
    
    def count_messages(self, user1: Optional[str] = None, user2: Optional[str] = None) -> int:
        """
        Count messages between users or total messages
        
        Args:
            user1: First user (optional)
            user2: Second user (optional)
        
        Returns:
            Message count
        """
        try:
            if user1 and user2:
                query = {
                    "$or": [
                        {"fromUser": user1, "toUser": user2},
                        {"fromUser": user2, "toUser": user1}
                    ]
                }
            elif user1:
                query = {"$or": [{"fromUser": user1}, {"toUser": user1}]}
            else:
                query = {}
            
            count = self.collection.count_documents(query)
            logger.info(f"Message count: {count}")
            return count
            
        except PyMongoError as e:
            logger.error(f"Failed to count messages: {e}")
            raise
    
    def health_check(self) -> bool:
        """
        Check if MongoDB is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            self.client.admin.command('ping')
            return True
        except PyMongoError:
            return False
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


# Global MongoDB handler instance (singleton pattern)
_db_instance: Optional[MongoDBHandler] = None


def get_db() -> MongoDBHandler:
    """
    Get or create the global MongoDB handler instance
    
    Returns:
        MongoDBHandler instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = MongoDBHandler()
    return _db_instance

