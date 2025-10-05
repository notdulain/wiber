#!/usr/bin/env python3
"""Debug script for topic cleanup."""

import time
import tempfile
import shutil
from src.replication.topics import TopicManager

def debug_cleanup():
    temp_dir = tempfile.mkdtemp()
    try:
        manager = TopicManager(temp_dir)
        manager.create_topic('short-retention', retention_hours=0.001)
        manager.publish_message('short-retention', {'key': 'value'})
        
        print('Before sleep:')
        topic_info = manager.topics['short-retention']
        print(f'  last_message_at: {topic_info["last_message_at"]}')
        print(f'  retention_hours: {topic_info["retention_hours"]}')
        
        time.sleep(0.002)
        
        print('After sleep:')
        current_time = time.time()
        last_message_at = topic_info['last_message_at']
        retention_seconds = topic_info['retention_hours'] * 3600
        
        print(f'  current_time: {current_time}')
        print(f'  last_message_at: {last_message_at}')
        print(f'  retention_seconds: {retention_seconds}')
        print(f'  time_diff: {current_time - last_message_at}')
        print(f'  should_cleanup: {(current_time - last_message_at) > retention_seconds}')
        
        cleaned = manager.cleanup_expired_topics()
        print(f'  cleaned_count: {cleaned}')
        
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    debug_cleanup()
