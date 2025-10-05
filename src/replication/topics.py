"""Topic management system for organizing messages by categories."""

import os
import json
import time
import structlog
from typing import Dict, List, Set, Any, Optional
from pathlib import Path

logger = structlog.get_logger(__name__)

# Import our commit log and deduplication systems
try:
    from src.replication.log import CommitLog
    from src.replication.dedup import MessageDeduplicator
except ImportError:
    # Fallback for testing or if modules not available
    CommitLog = None
    MessageDeduplicator = None


class TopicManager:
    """Manages topics and their associated commit logs."""
    
    def __init__(self, log_dir: str = "data", enable_dedup: bool = True):
        """Initialize the topic manager.
        
        Args:
            log_dir: Directory to store topic logs
            enable_dedup: Whether to enable deduplication for topics
        """
        self.log_dir = Path(log_dir)
        self.enable_dedup = enable_dedup
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Topic registry: {topic_name: TopicInfo}
        self.topics: Dict[str, Dict[str, Any]] = {}
        
        # Active commit logs: {topic_name: CommitLog}
        self.commit_logs: Dict[str, CommitLog] = {}
        
        # Topic metadata file
        self.metadata_file = self.log_dir / "topics.json"
        
        # Load existing topics
        self._load_topic_metadata()
        
        logger.info(f"TopicManager initialized", 
                   log_dir=str(self.log_dir),
                   topics_count=len(self.topics),
                   deduplication_enabled=enable_dedup)
    
    def _load_topic_metadata(self) -> None:
        """Load topic metadata from disk."""
        if not self.metadata_file.exists():
            logger.debug(f"Topic metadata file {self.metadata_file} does not exist, starting fresh")
            return
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.topics = data.get('topics', {})
            
            # Initialize commit logs for existing topics
            for topic_name in self.topics.keys():
                self._initialize_commit_log(topic_name)
            
            logger.info(f"Loaded {len(self.topics)} topics from metadata")
            
        except Exception as e:
            logger.error(f"Failed to load topic metadata: {e}")
            self.topics = {}
    
    def _save_topic_metadata(self) -> None:
        """Save topic metadata to disk."""
        try:
            data = {
                "topics": self.topics,
                "last_updated": time.time()
            }
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved topic metadata to {self.metadata_file}")
            
        except Exception as e:
            logger.error(f"Failed to save topic metadata: {e}")
    
    def _initialize_commit_log(self, topic_name: str) -> None:
        """Initialize commit log for a topic."""
        if not CommitLog:
            logger.warning("CommitLog not available, cannot initialize topic log")
            return
        
        try:
            commit_log = CommitLog(
                log_dir=str(self.log_dir),
                topic=topic_name,
                enable_dedup=self.enable_dedup
            )
            self.commit_logs[topic_name] = commit_log
            logger.debug(f"Initialized commit log for topic '{topic_name}'")
            
        except Exception as e:
            logger.error(f"Failed to initialize commit log for topic '{topic_name}': {e}")
    
    def create_topic(self, topic_name: str, description: str = "", 
                    retention_hours: int = 24, max_size_mb: int = 100) -> bool:
        """Create a new topic.
        
        Args:
            topic_name: Name of the topic to create
            description: Description of the topic
            retention_hours: How long to retain messages (hours)
            max_size_mb: Maximum size of topic log (MB)
            
        Returns:
            True if topic was created successfully, False otherwise
        """
        # Validate topic name
        if not self._is_valid_topic_name(topic_name):
            logger.warning(f"Invalid topic name: {topic_name}")
            return False
        
        # Check if topic already exists
        if topic_name in self.topics:
            logger.warning(f"Topic '{topic_name}' already exists")
            return False
        
        # Create topic metadata
        topic_info = {
            "name": topic_name,
            "description": description,
            "created_at": time.time(),
            "retention_hours": retention_hours,
            "max_size_mb": max_size_mb,
            "message_count": 0,
            "last_message_at": None,
            "status": "active"
        }
        
        # Add to topics registry
        self.topics[topic_name] = topic_info
        
        # Initialize commit log
        self._initialize_commit_log(topic_name)
        
        # Save metadata
        self._save_topic_metadata()
        
        logger.info(f"Created topic '{topic_name}'", 
                   description=description,
                   retention_hours=retention_hours,
                   max_size_mb=max_size_mb)
        
        return True
    
    def delete_topic(self, topic_name: str, force: bool = False) -> bool:
        """Delete a topic.
        
        Args:
            topic_name: Name of the topic to delete
            force: If True, delete even if topic has messages
            
        Returns:
            True if topic was deleted successfully, False otherwise
        """
        if topic_name not in self.topics:
            logger.warning(f"Topic '{topic_name}' does not exist")
            return False
        
        # Check if topic has messages
        if topic_name in self.commit_logs:
            commit_log = self.commit_logs[topic_name]
            if commit_log.get_entry_count() > 0 and not force:
                logger.warning(f"Cannot delete topic '{topic_name}' with {commit_log.get_entry_count()} messages. Use force=True")
                return False
        
        # Close commit log
        if topic_name in self.commit_logs:
            self.commit_logs[topic_name].close()
            del self.commit_logs[topic_name]
        
        # Remove from topics registry
        del self.topics[topic_name]
        
        # Save metadata
        self._save_topic_metadata()
        
        logger.info(f"Deleted topic '{topic_name}'")
        return True
    
    def list_topics(self) -> List[Dict[str, Any]]:
        """List all topics with their metadata.
        
        Returns:
            List of topic information dictionaries
        """
        topics_list = []
        for topic_name, topic_info in self.topics.items():
            # Add current statistics
            topic_data = topic_info.copy()
            
            if topic_name in self.commit_logs:
                commit_log = self.commit_logs[topic_name]
                topic_data.update({
                    "current_message_count": commit_log.get_entry_count(),
                    "latest_offset": commit_log.get_latest_offset(),
                    "log_size_bytes": commit_log.get_log_info().get("log_size_bytes", 0)
                })
            
            topics_list.append(topic_data)
        
        return topics_list
    
    def get_topic_info(self, topic_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a topic.
        
        Args:
            topic_name: Name of the topic
            
        Returns:
            Topic information dictionary or None if topic doesn't exist
        """
        if topic_name not in self.topics:
            return None
        
        topic_info = self.topics[topic_name].copy()
        
        # Add current statistics
        if topic_name in self.commit_logs:
            commit_log = self.commit_logs[topic_name]
            log_info = commit_log.get_log_info()
            topic_info.update(log_info)
        
        return topic_info
    
    def publish_message(self, topic_name: str, message: Dict[str, Any]) -> int:
        """Publish a message to a topic.
        
        Args:
            topic_name: Name of the topic
            message: Message data to publish
            
        Returns:
            Offset where message was stored, or -1 if failed/duplicate
        """
        if topic_name not in self.topics:
            logger.warning(f"Topic '{topic_name}' does not exist")
            return -1
        
        if topic_name not in self.commit_logs:
            logger.error(f"Commit log for topic '{topic_name}' not initialized")
            return -1
        
        # Publish to commit log
        commit_log = self.commit_logs[topic_name]
        offset = commit_log.append(message)
        
        # Update topic metadata
        if offset >= 0:  # Success
            self.topics[topic_name]["message_count"] += 1
            self.topics[topic_name]["last_message_at"] = time.time()
            self._save_topic_metadata()
            
            logger.debug(f"Published message to topic '{topic_name}' at offset {offset}")
        
        return offset
    
    def read_messages(self, topic_name: str, offset: int = 0, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read messages from a topic.
        
        Args:
            topic_name: Name of the topic
            offset: Starting offset
            limit: Maximum number of messages to return
            
        Returns:
            List of log entries
        """
        if topic_name not in self.commit_logs:
            logger.warning(f"Topic '{topic_name}' does not exist")
            return []
        
        commit_log = self.commit_logs[topic_name]
        return commit_log.read(offset, limit)
    
    def get_topic_stats(self, topic_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a topic.
        
        Args:
            topic_name: Name of the topic
            
        Returns:
            Statistics dictionary or None if topic doesn't exist
        """
        if topic_name not in self.commit_logs:
            return None
        
        commit_log = self.commit_logs[topic_name]
        return commit_log.get_log_info()
    
    def _is_valid_topic_name(self, topic_name: str) -> bool:
        """Validate topic name.
        
        Args:
            topic_name: Topic name to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not topic_name or not isinstance(topic_name, str):
            return False
        
        # Check length
        if len(topic_name) < 1 or len(topic_name) > 100:
            return False
        
        # Check characters (alphanumeric, hyphens, underscores)
        if not topic_name.replace('-', '').replace('_', '').isalnum():
            return False
        
        # Cannot start with hyphen or underscore
        if topic_name.startswith('-') or topic_name.startswith('_'):
            return False
        
        # Cannot end with hyphen or underscore
        if topic_name.endswith('-') or topic_name.endswith('_'):
            return False
        
        return True
    
    def cleanup_expired_topics(self) -> int:
        """Clean up topics that have exceeded their retention period.
        
        Returns:
            Number of topics cleaned up
        """
        current_time = time.time()
        cleaned_count = 0
        
        for topic_name, topic_info in list(self.topics.items()):
            retention_seconds = topic_info.get("retention_hours", 24) * 3600
            last_message_at = topic_info.get("last_message_at")
            
            # If topic has messages and last message is older than retention period
            if last_message_at and (current_time - last_message_at) > retention_seconds:
                logger.info(f"Cleaning up expired topic '{topic_name}' (last message {current_time - last_message_at:.2f}s ago)")
                self.delete_topic(topic_name, force=True)
                cleaned_count += 1
            # If topic has no messages and was created more than retention period ago
            elif not last_message_at:
                created_at = topic_info.get("created_at", current_time)
                if (current_time - created_at) > retention_seconds:
                    logger.info(f"Cleaning up unused topic '{topic_name}' (created {current_time - created_at:.2f}s ago)")
                    self.delete_topic(topic_name, force=True)
                    cleaned_count += 1
        
        return cleaned_count
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """Get overall topic manager statistics.
        
        Returns:
            Statistics dictionary
        """
        total_messages = 0
        total_size_bytes = 0
        active_topics = 0
        
        for topic_name in self.topics.keys():
            if topic_name in self.commit_logs:
                commit_log = self.commit_logs[topic_name]
                log_info = commit_log.get_log_info()
                total_messages += log_info.get("entries_count", 0)
                total_size_bytes += log_info.get("log_size_bytes", 0)
                active_topics += 1
        
        return {
            "total_topics": len(self.topics),
            "active_topics": active_topics,
            "total_messages": total_messages,
            "total_size_bytes": total_size_bytes,
            "deduplication_enabled": self.enable_dedup,
            "log_directory": str(self.log_dir)
        }
    
    def close(self) -> None:
        """Close all topic logs and save metadata."""
        logger.info(f"Closing TopicManager with {len(self.commit_logs)} active topics")
        
        # Close all commit logs
        for topic_name, commit_log in self.commit_logs.items():
            try:
                commit_log.close()
            except Exception as e:
                logger.error(f"Error closing commit log for topic '{topic_name}': {e}")
        
        # Save final metadata
        self._save_topic_metadata()
        
        logger.info("TopicManager closed successfully")
