"""Persistent commit log for message storage."""

import os
import json
import time
import structlog
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = structlog.get_logger(__name__)

# Import deduplication system
try:
    from src.replication.dedup import MessageDeduplicator
except ImportError:
    # Fallback for testing or if module not available
    MessageDeduplicator = None


class CommitLog:
    """Append-only log for persistent message storage."""
    
    def __init__(self, log_dir: str = "data", topic: str = "default", enable_dedup: bool = True):
        """Initialize the commit log.
        
        Args:
            log_dir: Directory to store log files
            topic: Topic name for this log
            enable_dedup: Whether to enable message deduplication
        """
        self.log_dir = Path(log_dir)
        self.topic = topic
        self.log_file = self.log_dir / f"{topic}.log"
        self.index_file = self.log_dir / f"{topic}.index"
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize log state
        self.entries: List[Dict[str, Any]] = []
        self.next_offset = 0
        
        # Initialize deduplication system
        self.deduplicator: Optional[MessageDeduplicator] = None
        if enable_dedup and MessageDeduplicator:
            try:
                self.deduplicator = MessageDeduplicator()
                logger.info(f"Deduplication enabled for topic '{topic}'")
            except Exception as e:
                logger.warning(f"Failed to initialize deduplicator: {e}")
                self.deduplicator = None
        
        # Load existing log if it exists
        self._load_existing_log()
        
        logger.info(f"CommitLog initialized for topic '{topic}'", 
                   log_file=str(self.log_file),
                   entries_count=len(self.entries),
                   next_offset=self.next_offset,
                   deduplication_enabled=self.deduplicator is not None)
    
    def _load_existing_log(self) -> None:
        """Load existing log entries from disk."""
        if not self.log_file.exists():
            logger.debug(f"Log file {self.log_file} does not exist, starting fresh")
            return
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        entry = json.loads(line)
                        # Validate entry structure
                        if not isinstance(entry, dict) or 'offset' not in entry:
                            logger.warning(f"Invalid entry structure at line {line_num}")
                            continue
                        self.entries.append(entry)
                        self.next_offset = max(self.next_offset, entry.get('offset', 0) + 1)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON in log file at line {line_num}: {e}")
                        continue
            
            logger.info(f"Loaded {len(self.entries)} entries from existing log")
            
        except Exception as e:
            logger.error(f"Failed to load existing log: {e}")
            # Start fresh if we can't load
            self.entries = []
            self.next_offset = 0
    
    def append(self, message: Dict[str, Any]) -> int:
        """Append a message to the log.
        
        Args:
            message: Message data to append
            
        Returns:
            Offset where the message was stored, or -1 if duplicate
        """
        # Check for duplicates if deduplication is enabled
        if self.deduplicator:
            if self.deduplicator.is_duplicate(message, self.topic):
                logger.debug(f"Duplicate message detected, skipping append", 
                            topic=self.topic,
                            message_keys=list(message.keys()) if isinstance(message, dict) else str(type(message)))
                return -1  # Indicate duplicate
        
        # Create log entry
        entry = {
            "offset": self.next_offset,
            "timestamp": time.time(),
            "topic": self.topic,
            "message": message
        }
        
        # Add to memory
        self.entries.append(entry)
        
        # Write to disk
        self._write_entry_to_disk(entry)
        
        # Add to deduplication cache if enabled
        if self.deduplicator:
            self.deduplicator.add_message(message, self.topic)
        
        # Update offset
        offset = self.next_offset
        self.next_offset += 1
        
        logger.debug(f"Appended message to log", 
                    offset=offset, 
                    topic=self.topic,
                    message_keys=list(message.keys()) if isinstance(message, dict) else str(type(message)))
        
        return offset
    
    def _write_entry_to_disk(self, entry: Dict[str, Any]) -> None:
        """Write a single entry to the log file."""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write entry to disk: {e}")
            raise
    
    def read(self, offset: int = 0, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read messages from the log.
        
        Args:
            offset: Starting offset (inclusive)
            limit: Maximum number of messages to return
            
        Returns:
            List of log entries
        """
        # Filter entries by offset
        filtered_entries = [entry for entry in self.entries if entry['offset'] >= offset]
        
        # Apply limit if specified
        if limit is not None:
            filtered_entries = filtered_entries[:limit]
        
        logger.debug(f"Read {len(filtered_entries)} entries from log", 
                    offset=offset, 
                    limit=limit,
                    topic=self.topic)
        
        return filtered_entries
    
    def read_range(self, start_offset: int, end_offset: int) -> List[Dict[str, Any]]:
        """Read messages in a specific range.
        
        Args:
            start_offset: Starting offset (inclusive)
            end_offset: Ending offset (exclusive)
            
        Returns:
            List of log entries in the range
        """
        filtered_entries = [
            entry for entry in self.entries 
            if start_offset <= entry['offset'] < end_offset
        ]
        
        logger.debug(f"Read {len(filtered_entries)} entries from range", 
                    start_offset=start_offset,
                    end_offset=end_offset,
                    topic=self.topic)
        
        return filtered_entries
    
    def get_latest_offset(self) -> int:
        """Get the latest offset in the log."""
        return self.next_offset - 1 if self.entries else -1
    
    def get_entry_count(self) -> int:
        """Get the total number of entries in the log."""
        return len(self.entries)
    
    def get_log_info(self) -> Dict[str, Any]:
        """Get information about the log."""
        info = {
            "topic": self.topic,
            "log_file": str(self.log_file),
            "entries_count": len(self.entries),
            "next_offset": self.next_offset,
            "latest_offset": self.get_latest_offset(),
            "log_size_bytes": self.log_file.stat().st_size if self.log_file.exists() else 0,
            "deduplication_enabled": self.deduplicator is not None
        }
        
        # Add deduplication statistics if available
        if self.deduplicator:
            dedup_stats = self.deduplicator.get_cache_stats()
            info["deduplication_stats"] = dedup_stats
        
        return info
    
    def truncate(self, offset: int) -> None:
        """Truncate the log at the specified offset.
        
        Args:
            offset: Offset to truncate at (entries with offset >= this will be removed)
        """
        # Remove entries from memory
        original_count = len(self.entries)
        self.entries = [entry for entry in self.entries if entry['offset'] < offset]
        
        # Update next_offset
        self.next_offset = offset
        
        # Rewrite the entire log file
        self._rewrite_log_file()
        
        logger.info(f"Truncated log at offset {offset}", 
                   removed_entries=original_count - len(self.entries),
                   remaining_entries=len(self.entries))
    
    def _rewrite_log_file(self) -> None:
        """Rewrite the entire log file with current entries."""
        try:
            # Write to temporary file first
            temp_file = self.log_file.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                for entry in self.entries:
                    f.write(json.dumps(entry) + '\n')
            
            # Replace original file
            temp_file.replace(self.log_file)
            
        except Exception as e:
            logger.error(f"Failed to rewrite log file: {e}")
            raise
    
    def close(self) -> None:
        """Close the log and flush any pending writes."""
        logger.info(f"Closing commit log for topic '{self.topic}'")
        # For now, we write immediately, so nothing to flush
        # In the future, we might add buffering