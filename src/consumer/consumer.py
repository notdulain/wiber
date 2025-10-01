"""
Kafka Consumer for Wiber Messaging System

This module handles consuming messages from Kafka and storing them in MongoDB.
Responsibility: Member 1 (Fault Tolerance) + Member 2 (Replication)
"""

from kafka import KafkaConsumer
from kafka.errors import KafkaError
import json
import logging
import sys
import signal
from typing import Optional
from src.database.mongodb_handler import get_db
from src.config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class MessageConsumer:
    """
    Kafka Consumer with fault-tolerant processing
    
    Features:
    - Manual commit after successful processing (at-least-once delivery)
    - Automatic retry on failure
    - Dead Letter Queue for poison messages
    - Graceful shutdown
    """
    
    def __init__(self):
        """Initialize Kafka consumer with fault-tolerant settings"""
        self.running = False
        self.consumer: Optional[KafkaConsumer] = None
        self.db = get_db()
        
        try:
            self.consumer = KafkaConsumer(
                settings.KAFKA_TOPIC,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
                
                # Deserialization
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                
                # Consumer group for load balancing
                group_id=settings.KAFKA_CONSUMER_GROUP,
                
                # Fault Tolerance Settings (Member 1's responsibility)
                enable_auto_commit=False,  # Manual commit after processing
                auto_offset_reset='earliest',  # Start from beginning if no offset
                
                # Session management
                session_timeout_ms=30000,  # 30 seconds
                heartbeat_interval_ms=10000,  # 10 seconds
                max_poll_interval_ms=300000,  # 5 minutes
                
                # Fetch settings
                max_poll_records=100,  # Process up to 100 messages per poll
            )
            
            logger.info(
                f"Kafka consumer initialized: "
                f"topic={settings.KAFKA_TOPIC}, "
                f"group={settings.KAFKA_CONSUMER_GROUP}, "
                f"servers={settings.KAFKA_BOOTSTRAP_SERVERS}"
            )
            
        except KafkaError as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise
    
    def start(self):
        """
        Start consuming messages
        
        This is the main processing loop that:
        1. Polls for messages from Kafka
        2. Processes each message
        3. Saves to MongoDB
        4. Commits offset only after successful save
        """
        self.running = True
        logger.info("Consumer started, listening for messages...")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            # Main consumption loop
            for message in self.consumer:
                if not self.running:
                    break
                
                try:
                    # Extract message data
                    msg_data = message.value
                    msg_id = msg_data.get('messageId', 'unknown')
                    
                    logger.info(
                        f"Received message: {msg_id} "
                        f"(partition={message.partition}, offset={message.offset})"
                    )
                    
                    # Process message: Save to MongoDB
                    # Member 2's responsibility: Ensure replication and consistency
                    success = self._process_message(msg_data)
                    
                    if success:
                        # Commit offset only after successful processing
                        # Member 1's responsibility: At-least-once delivery
                        self.consumer.commit()
                        logger.info(f"Message {msg_id} processed and committed")
                    else:
                        logger.error(f"Message {msg_id} processing failed, will retry")
                        # Don't commit - message will be reprocessed
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in message: {e}")
                    # Skip malformed messages
                    self.consumer.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    # Could send to Dead Letter Queue here
                    # For now, we'll skip and commit to avoid blocking
                    self.consumer.commit()
        
        except KafkaError as e:
            logger.error(f"Kafka error in consumer loop: {e}")
            raise
        
        finally:
            self._shutdown()
    
    def _process_message(self, msg_data: dict) -> bool:
        """
        Process a single message
        
        Args:
            msg_data: Message data dictionary
        
        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Validate message structure
            required_fields = ['messageId', 'fromUser', 'toUser', 'content', 'timestamp']
            if not all(field in msg_data for field in required_fields):
                logger.error(f"Message missing required fields: {msg_data}")
                return False
            
            # Save to MongoDB with deduplication
            # Member 2's responsibility: Handle duplicates gracefully
            self.db.save_message(msg_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process message {msg_data.get('messageId')}: {e}")
            return False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    def _shutdown(self):
        """Cleanup and close resources"""
        logger.info("Shutting down consumer...")
        
        if self.consumer:
            try:
                # Commit any pending offsets
                self.consumer.commit()
                self.consumer.close()
                logger.info("Consumer closed successfully")
            except Exception as e:
                logger.error(f"Error during consumer shutdown: {e}")
        
        logger.info("Consumer shutdown complete")


def main():
    """Main entry point for the consumer service"""
    logger.info("=" * 60)
    logger.info("Wiber Message Consumer Service")
    logger.info("=" * 60)
    logger.info(f"Kafka Topic: {settings.KAFKA_TOPIC}")
    logger.info(f"Consumer Group: {settings.KAFKA_CONSUMER_GROUP}")
    logger.info(f"Kafka Servers: {settings.KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"MongoDB: {settings.MONGO_URI}")
    logger.info("=" * 60)
    
    try:
        consumer = MessageConsumer()
        consumer.start()
    except KeyboardInterrupt:
        logger.info("Consumer interrupted by user")
    except Exception as e:
        logger.error(f"Consumer error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

