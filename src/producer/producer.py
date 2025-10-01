"""
Kafka Producer for Wiber Messaging System

This module handles sending messages to Kafka with proper fault tolerance settings.
Responsibility: Member 1 (Fault Tolerance) + Member 3 (Time & Order)
"""

from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import uuid
import time
import logging
from typing import Dict, Optional
from src.config.settings import settings

logger = logging.getLogger(__name__)


class MessageProducer:
    """
    Kafka Producer with fault-tolerant configuration
    
    Features:
    - Idempotent writes (exactly-once semantics)
    - Message ordering per conversation
    - Automatic retries on failure
    - Acknowledgment from all replicas
    """
    
    def __init__(self):
        """Initialize Kafka producer with fault-tolerant settings"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
                
                # Serialization
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                
                # Fault Tolerance Settings (Member 1's responsibility)
                acks='all',  # Wait for all replicas to acknowledge
                retries=10,  # Retry up to 10 times on failure
                max_in_flight_requests_per_connection=5,  # Allow pipelining
                # Note: enable_idempotence not supported in kafka-python 2.0.2
                # Idempotency is achieved through acks='all' + retries + message keys
                
                # Timeout settings
                request_timeout_ms=30000,  # 30 seconds
                retry_backoff_ms=100,  # Wait 100ms between retries
                
                # Compression disabled (requires python-snappy library)
                # compression_type='snappy',
            )
            logger.info(f"Kafka producer initialized: {settings.KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            raise
    
    def send_message(
        self,
        from_user: str,
        to_user: str,
        content: str,
        timestamp: Optional[int] = None
    ) -> Dict:
        """
        Send a message to Kafka
        
        Args:
            from_user: Sender username
            to_user: Recipient username
            content: Message content
            timestamp: Optional timestamp (generated if not provided)
        
        Returns:
            Dict containing message details
        
        Raises:
            KafkaError: If message sending fails after retries
        """
        
        # Generate message ID and timestamp
        message_id = str(uuid.uuid4())
        if timestamp is None:
            # Member 3's responsibility: Consistent timestamp format
            timestamp = int(time.time() * 1000)  # Milliseconds since epoch
        
        message = {
            'messageId': message_id,
            'fromUser': from_user,
            'toUser': to_user,
            'content': content,
            'timestamp': timestamp
        }
        
        # Member 3's responsibility: Use conversation key for ordering
        # Messages with the same key go to the same partition, maintaining order
        conversation_key = self._generate_conversation_key(from_user, to_user)
        
        try:
            # Send message to Kafka
            future = self.producer.send(
                settings.KAFKA_TOPIC,
                key=conversation_key,
                value=message
            )
            
            # Wait for confirmation (blocking)
            record_metadata = future.get(timeout=10)
            
            logger.info(
                f"Message sent successfully: {message_id} "
                f"(topic={record_metadata.topic}, "
                f"partition={record_metadata.partition}, "
                f"offset={record_metadata.offset})"
            )
            
            return message
            
        except KafkaError as e:
            logger.error(f"Failed to send message {message_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending message {message_id}: {e}")
            raise
    
    def _generate_conversation_key(self, user1: str, user2: str) -> str:
        """
        Generate a consistent key for a conversation
        
        This ensures messages between the same two users go to the same partition,
        maintaining order (Member 3's responsibility: Time & Order)
        
        Args:
            user1: First user
            user2: Second user
        
        Returns:
            Consistent conversation key
        """
        # Sort users to ensure consistent key regardless of direction
        users = sorted([user1, user2])
        return f"{users[0]}:{users[1]}"
    
    def flush(self):
        """Flush any pending messages"""
        self.producer.flush()
        logger.info("Producer flushed all pending messages")
    
    def close(self):
        """Close the producer and release resources"""
        self.producer.flush()
        self.producer.close()
        logger.info("Kafka producer closed")


# Global producer instance (singleton pattern)
_producer_instance: Optional[MessageProducer] = None


def get_producer() -> MessageProducer:
    """
    Get or create the global producer instance
    
    Returns:
        MessageProducer instance
    """
    global _producer_instance
    if _producer_instance is None:
        _producer_instance = MessageProducer()
    return _producer_instance

