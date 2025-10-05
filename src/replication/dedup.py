"""Message deduplication system."""

import hashlib
import json
import time
import structlog
from typing import Dict, Set, Any, Optional
from collections import defaultdict

logger = structlog.get_logger(__name__)


class MessageDeduplicator:
    """Message deduplication system using message ID caching."""
    
    def __init__(self, cache_size: int = 10000, ttl_seconds: int = 3600):
        """Initialize the message deduplicator.
        
        Args:
            cache_size: Maximum number of message IDs to cache
            ttl_seconds: Time-to-live for cached message IDs in seconds
        """
        self.cache_size = cache_size
        self.ttl_seconds = ttl_seconds
        
        # Message ID cache: {message_id: timestamp}
        self.message_cache: Dict[str, float] = {}
        
        # Topic-based caches for better organization
        self.topic_caches: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Statistics
        self.total_messages_processed = 0
        self.duplicate_messages_detected = 0
        
        logger.info(f"MessageDeduplicator initialized", 
                   cache_size=cache_size,
                   ttl_seconds=ttl_seconds)
    
    def generate_message_id(self, message: Dict[str, Any], topic: str = "default") -> str:
        """Generate a unique message ID based on content and topic.
        
        Args:
            message: Message content
            topic: Topic name
            
        Returns:
            Unique message ID string
        """
        # Create a deterministic hash of the message content
        # Include topic to ensure same message in different topics gets different ID
        content = {
            "topic": topic,
            "message": message
        }
        
        # Sort keys for consistent hashing
        content_str = json.dumps(content, sort_keys=True, separators=(',', ':'))
        
        # Generate SHA-256 hash
        message_id = hashlib.sha256(content_str.encode('utf-8')).hexdigest()
        
        logger.debug(f"Generated message ID", 
                    message_id=message_id[:16] + "...",
                    topic=topic,
                    content_keys=list(message.keys()) if isinstance(message, dict) else str(type(message)))
        
        return message_id
    
    def is_duplicate(self, message: Dict[str, Any], topic: str = "default") -> bool:
        """Check if a message is a duplicate.
        
        Args:
            message: Message content to check
            topic: Topic name
            
        Returns:
            True if message is a duplicate, False otherwise
        """
        message_id = self.generate_message_id(message, topic)
        current_time = time.time()
        
        # Check global cache first
        if message_id in self.message_cache:
            cache_time = self.message_cache[message_id]
            if current_time - cache_time < self.ttl_seconds:
                logger.debug(f"Duplicate message detected in global cache", 
                            message_id=message_id[:16] + "...",
                            topic=topic)
                self.duplicate_messages_detected += 1
                return True
        
        # Check topic-specific cache
        topic_cache = self.topic_caches[topic]
        if message_id in topic_cache:
            cache_time = topic_cache[message_id]
            if current_time - cache_time < self.ttl_seconds:
                logger.debug(f"Duplicate message detected in topic cache", 
                            message_id=message_id[:16] + "...",
                            topic=topic)
                self.duplicate_messages_detected += 1
                return True
        
        # Not a duplicate
        return False
    
    def add_message(self, message: Dict[str, Any], topic: str = "default") -> str:
        """Add a message to the deduplication cache.
        
        Args:
            message: Message content
            topic: Topic name
            
        Returns:
            Message ID
        """
        message_id = self.generate_message_id(message, topic)
        current_time = time.time()
        
        # Add to global cache
        self.message_cache[message_id] = current_time
        
        # Add to topic-specific cache
        self.topic_caches[topic][message_id] = current_time
        
        # Update statistics
        self.total_messages_processed += 1
        
        # Clean up old entries if cache is full
        self._cleanup_cache()
        
        logger.debug(f"Added message to deduplication cache", 
                    message_id=message_id[:16] + "...",
                    topic=topic,
                    cache_size=len(self.message_cache))
        
        return message_id
    
    def _cleanup_cache(self) -> None:
        """Clean up expired entries from the cache."""
        current_time = time.time()
        
        # Clean global cache
        expired_ids = [
            msg_id for msg_id, timestamp in self.message_cache.items()
            if current_time - timestamp > self.ttl_seconds
        ]
        
        for msg_id in expired_ids:
            del self.message_cache[msg_id]
        
        # Clean topic caches
        for topic in list(self.topic_caches.keys()):
            topic_cache = self.topic_caches[topic]
            expired_ids = [
                msg_id for msg_id, timestamp in topic_cache.items()
                if current_time - timestamp > self.ttl_seconds
            ]
            
            for msg_id in expired_ids:
                del topic_cache[msg_id]
            
            # Remove empty topic caches
            if not topic_cache:
                del self.topic_caches[topic]
        
        # If still over cache size, remove oldest entries
        if len(self.message_cache) > self.cache_size:
            # Sort by timestamp and remove oldest
            sorted_entries = sorted(
                self.message_cache.items(),
                key=lambda x: x[1]
            )
            
            entries_to_remove = len(self.message_cache) - self.cache_size
            for msg_id, _ in sorted_entries[:entries_to_remove]:
                del self.message_cache[msg_id]
        
        if expired_ids:
            logger.debug(f"Cleaned up {len(expired_ids)} expired entries from cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get deduplication cache statistics."""
        current_time = time.time()
        
        # Count active entries
        active_global = sum(
            1 for timestamp in self.message_cache.values()
            if current_time - timestamp < self.ttl_seconds
        )
        
        active_topic = {}
        for topic, cache in self.topic_caches.items():
            active_topic[topic] = sum(
                1 for timestamp in cache.values()
                if current_time - timestamp < self.ttl_seconds
            )
        
        return {
            "total_messages_processed": self.total_messages_processed,
            "duplicate_messages_detected": self.duplicate_messages_detected,
            "duplicate_rate": (
                self.duplicate_messages_detected / self.total_messages_processed
                if self.total_messages_processed > 0 else 0
            ),
            "cache_size": len(self.message_cache),
            "active_entries": active_global,
            "topic_stats": active_topic,
            "cache_size_limit": self.cache_size,
            "ttl_seconds": self.ttl_seconds
        }
    
    def clear_cache(self, topic: Optional[str] = None) -> None:
        """Clear the deduplication cache.
        
        Args:
            topic: If specified, only clear cache for this topic. If None, clear all.
        """
        if topic is None:
            # Clear all caches
            self.message_cache.clear()
            self.topic_caches.clear()
            logger.info("Cleared all deduplication caches")
        else:
            # Clear specific topic cache
            if topic in self.topic_caches:
                del self.topic_caches[topic]
                logger.info(f"Cleared deduplication cache for topic '{topic}'")
            
            # Remove topic-specific entries from global cache
            # This is a bit expensive, but ensures consistency
            topic_entries_to_remove = []
            for msg_id in self.message_cache.keys():
                # We can't easily determine topic from message_id alone
                # So we'll leave global cache as-is for now
                pass
    
    def is_message_id_cached(self, message_id: str, topic: str = "default") -> bool:
        """Check if a specific message ID is cached.
        
        Args:
            message_id: Message ID to check
            topic: Topic name
            
        Returns:
            True if message ID is cached and not expired
        """
        current_time = time.time()
        
        # Check global cache
        if message_id in self.message_cache:
            cache_time = self.message_cache[message_id]
            if current_time - cache_time < self.ttl_seconds:
                return True
        
        # Check topic cache
        if topic in self.topic_caches:
            topic_cache = self.topic_caches[topic]
            if message_id in topic_cache:
                cache_time = topic_cache[message_id]
                if current_time - cache_time < self.ttl_seconds:
                    return True
        
        return False
    
    def get_cached_message_ids(self, topic: Optional[str] = None) -> Set[str]:
        """Get all cached message IDs.
        
        Args:
            topic: If specified, only return IDs for this topic
            
        Returns:
            Set of cached message IDs
        """
        current_time = time.time()
        
        if topic is None:
            # Return all active message IDs
            return {
                msg_id for msg_id, timestamp in self.message_cache.items()
                if current_time - timestamp < self.ttl_seconds
            }
        else:
            # Return topic-specific message IDs
            if topic not in self.topic_caches:
                return set()
            
            topic_cache = self.topic_caches[topic]
            return {
                msg_id for msg_id, timestamp in topic_cache.items()
                if current_time - timestamp < self.ttl_seconds
            }