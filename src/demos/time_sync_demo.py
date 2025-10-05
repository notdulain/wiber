#!/usr/bin/env python3
"""
Time Synchronization Demonstration for Manual Distributed System

This script demonstrates the time synchronization capabilities in the
manual distributed system without Kafka or Docker.
"""

import time
import threading
import argparse
from src.time.lamport import LamportClock, VectorClock, MessageOrdering
from src.time.sync import TimeSyncClient, TimeSyncServer, BoundedReordering, TimeSyncConfig


def demonstrate_lamport_clocks():
    """Demonstrate Lamport clock functionality."""
    print("=== LAMPORT CLOCK DEMONSTRATION ===\n")
    
    # Create three nodes with Lamport clocks
    dulain_clock = LamportClock()
    luchitha_clock = LamportClock()
    sanuk_clock = LamportClock()
    
    print("Simulating message exchange with Lamport clocks...")
    
    # Dulain sends message 1
    dulain_time = dulain_clock.tick()
    print(f"Dulain sends message: logical time = {dulain_time}")
    
    # Luchitha receives Dulain's message and sends his own
    luchitha_clock.update(dulain_time)
    luchitha_time = luchitha_clock.tick()
    print(f"Luchitha receives Dulain's message and sends: logical time = {luchitha_time}")
    
    # Sanuk sends message without receiving others
    sanuk_time = sanuk_clock.tick()
    print(f"Sanuk sends message: logical time = {sanuk_time}")
    
    # Dulain receives Luchitha's message and sends another
    dulain_clock.update(luchitha_time)
    dulain_time2 = dulain_clock.tick()
    print(f"Dulain receives Luchitha's message and sends: logical time = {dulain_time2}")
    
    print(f"\nFinal clock states:")
    print(f"  Dulain: {dulain_clock.get_time()}")
    print(f"  Luchitha: {luchitha_clock.get_time()}")
    print(f"  Sanuk: {sanuk_clock.get_time()}")


def demonstrate_vector_clocks():
    """Demonstrate vector clock functionality."""
    print("\n=== VECTOR CLOCK DEMONSTRATION ===\n")
    
    # Create three nodes with vector clocks
    dulain_clock = VectorClock("dulain", 3)
    luchitha_clock = VectorClock("luchitha", 3)
    sanuk_clock = VectorClock("sanuk", 3)
    
    print("Simulating message exchange with vector clocks...")
    
    # Dulain sends message
    dulain_vector = dulain_clock.tick()
    print(f"Dulain sends message: vector = {dulain_vector}")
    
    # Luchitha receives and sends
    luchitha_clock.update(dulain_vector)
    luchitha_vector = luchitha_clock.tick()
    print(f"Luchitha receives Dulain's message and sends: vector = {luchitha_vector}")
    
    # Sanuk sends without receiving
    sanuk_vector = sanuk_clock.tick()
    print(f"Sanuk sends message: vector = {sanuk_vector}")
    
    # Dulain receives Luchitha's message
    dulain_clock.update(luchitha_vector)
    dulain_vector2 = dulain_clock.tick()
    print(f"Dulain receives Luchitha's message and sends: vector = {dulain_vector2}")
    
    print(f"\nFinal vector clock states:")
    print(f"  Dulain: {dulain_clock.get_time()}")
    print(f"  Luchitha: {luchitha_clock.get_time()}")
    print(f"  Sanuk: {sanuk_clock.get_time()}")
    
    # Show causal relationships
    print(f"\nCausal relationships:")
    print(f"  Dulain's first -> Luchitha's message: {dulain_clock.compare(luchitha_vector)}")
    print(f"  Dulain's first -> Sanuk's message: {dulain_clock.compare(sanuk_vector)}")
    print(f"  Luchitha's message -> Dulain's second: {luchitha_clock.compare(dulain_vector2)}")


def demonstrate_time_sync():
    """Demonstrate time synchronization between nodes."""
    print("\n=== TIME SYNCHRONIZATION DEMONSTRATION ===\n")
    
    # Start time sync servers
    server1 = TimeSyncServer("server1", port=9201)
    server2 = TimeSyncServer("server2", port=9202)
    
    server1.start()
    server2.start()
    time.sleep(0.2)  # Give servers time to start
    
    try:
        # Create time sync client
        client = TimeSyncClient("client")
        
        print("Measuring clock offsets...")
        
        # Measure offset to server1
        offset1 = client.measure_offset("127.0.0.1", 9201, "server1")
        print(f"Offset to server1: {offset1:.6f} seconds")
        
        # Measure offset to server2
        offset2 = client.measure_offset("127.0.0.1", 9202, "server2")
        print(f"Offset to server2: {offset2:.6f} seconds")
        
        # Show synchronized time
        avg_offset = client.get_average_offset()
        sync_time = client.get_synchronized_time()
        current_time = time.time()
        
        print(f"\nTime synchronization results:")
        print(f"  Average offset: {avg_offset:.6f} seconds")
        print(f"  Current time: {current_time:.6f}")
        print(f"  Synchronized time: {sync_time:.6f}")
        print(f"  Difference: {abs(sync_time - current_time):.6f} seconds")
        
    finally:
        server1.stop()
        server2.stop()


def demonstrate_bounded_reordering():
    """Demonstrate bounded reordering system."""
    print("\n=== BOUNDED REORDERING DEMONSTRATION ===\n")
    
    reordering = BoundedReordering(max_delay_ms=100)
    
    print("Simulating message arrival with different timestamps...")
    
    # Create messages with different timestamps
    current_time = time.time()
    messages = [
        {"id": "msg1", "content": "First message", "timestamp": current_time - 0.2},  # 200ms ago
        {"id": "msg2", "content": "Second message", "timestamp": current_time - 0.1},  # 100ms ago
        {"id": "msg3", "content": "Third message", "timestamp": current_time - 0.05},  # 50ms ago
        {"id": "msg4", "content": "Fourth message", "timestamp": current_time},  # now
    ]
    
    print("Adding messages to reordering system...")
    for msg in messages:
        ready = reordering.add_message(msg)
        print(f"  Added {msg['id']}: {len(ready)} messages ready for delivery")
        
        for ready_msg in ready:
            print(f"    -> Delivering: {ready_msg['id']} - {ready_msg['content']}")
    
    print(f"\nPending messages: {reordering.get_pending_count()}")
    
    # Wait and check again
    print("\nWaiting 60ms and checking again...")
    time.sleep(0.06)
    
    # Add a new message to trigger re-evaluation
    new_msg = {"id": "msg5", "content": "New message", "timestamp": time.time()}
    ready = reordering.add_message(new_msg)
    
    print(f"Added new message: {len(ready)} messages ready for delivery")
    for ready_msg in ready:
        print(f"  -> Delivering: {ready_msg['id']} - {ready_msg['content']}")
    
    print(f"Remaining pending messages: {reordering.get_pending_count()}")


def demonstrate_message_ordering():
    """Demonstrate message ordering system."""
    print("\n=== MESSAGE ORDERING SYSTEM DEMONSTRATION ===\n")
    
    # Create message ordering systems for three nodes
    dulain_ordering = MessageOrdering("dulain", use_vector_clocks=False)
    luchitha_ordering = MessageOrdering("luchitha", use_vector_clocks=False)
    sanuk_ordering = MessageOrdering("sanuk", use_vector_clocks=False)
    
    print("Simulating message exchange with ordering system...")
    
    # Dulain sends message
    dulain_timestamp = dulain_ordering.create_timestamp()
    print(f"Dulain sends message: {dulain_timestamp}")
    
    # Luchitha receives and sends
    luchitha_ordering.update_from_message(dulain_timestamp)
    luchitha_timestamp = luchitha_ordering.create_timestamp()
    print(f"Luchitha receives Dulain's message and sends: {luchitha_timestamp}")
    
    # Sanuk sends without receiving
    sanuk_timestamp = sanuk_ordering.create_timestamp()
    print(f"Sanuk sends message: {sanuk_timestamp}")
    
    # Dulain receives Luchitha's message
    dulain_ordering.update_from_message(luchitha_timestamp)
    dulain_timestamp2 = dulain_ordering.create_timestamp()
    print(f"Dulain receives Luchitha's message and sends: {dulain_timestamp2}")
    
    print(f"\nCurrent time states:")
    print(f"  Dulain: {dulain_ordering.get_current_time()}")
    print(f"  Luchitha: {luchitha_ordering.get_current_time()}")
    print(f"  Sanuk: {sanuk_ordering.get_current_time()}")


def demonstrate_concurrent_operations():
    """Demonstrate concurrent operations and thread safety."""
    print("\n=== CONCURRENT OPERATIONS DEMONSTRATION ===\n")
    
    clock = LamportClock()
    results = []
    
    def worker(worker_id: int, num_operations: int):
        """Worker function for concurrent operations."""
        for i in range(num_operations):
            time_val = clock.tick()
            results.append((worker_id, i, time_val))
            time.sleep(0.001)  # Small delay
    
    print("Starting concurrent operations on Lamport clock...")
    
    # Start multiple worker threads
    threads = []
    for i in range(3):
        thread = threading.Thread(target=worker, args=(i, 5))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    print(f"Completed {len(results)} operations from 3 threads")
    print("Results (worker_id, operation, logical_time):")
    for worker_id, op_id, time_val in results:
        print(f"  Worker {worker_id}, Op {op_id}: {time_val}")
    
    # Verify all logical times are unique and sequential
    time_values = [time_val for _, _, time_val in results]
    unique_times = set(time_values)
    
    print(f"\nVerification:")
    print(f"  Total operations: {len(results)}")
    print(f"  Unique logical times: {len(unique_times)}")
    print(f"  All times unique: {len(time_values) == len(unique_times)}")
    print(f"  Time range: {min(time_values)} to {max(time_values)}")


def main():
    """Main demonstration function."""
    parser = argparse.ArgumentParser(description="Time Synchronization Demonstration")
    parser.add_argument("--demo", choices=[
        "lamport", "vector", "sync", "reordering", "ordering", "concurrent", "all"
    ], default="all", help="Which demonstration to run")
    
    args = parser.parse_args()
    
    print("Time Synchronization Demonstration")
    print("Manual Distributed System (No Kafka/Docker)")
    print("=" * 60)
    
    if args.demo in ["lamport", "all"]:
        demonstrate_lamport_clocks()
    
    if args.demo in ["vector", "all"]:
        demonstrate_vector_clocks()
    
    if args.demo in ["sync", "all"]:
        demonstrate_time_sync()
    
    if args.demo in ["reordering", "all"]:
        demonstrate_bounded_reordering()
    
    if args.demo in ["ordering", "all"]:
        demonstrate_message_ordering()
    
    if args.demo in ["concurrent", "all"]:
        demonstrate_concurrent_operations()
    
    print("\n" + "=" * 60)
    print("Demonstration complete!")
    print("\nKey Features Demonstrated:")
    print("✓ Lamport clocks for causal ordering")
    print("✓ Vector clocks for complete causal ordering")
    print("✓ SNTP-style time synchronization")
    print("✓ Bounded reordering for message delivery")
    print("✓ Thread-safe concurrent operations")
    print("✓ Message ordering with time sync")


if __name__ == "__main__":
    main()
