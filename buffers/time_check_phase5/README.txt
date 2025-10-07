Snapshot of Phase 5 (Time Synchronization) artifacts from branch 'time-check'.

Included files:
- src/time/sync.py            (SNTP-style offset, TimeSyncClient/Server, BoundedReordering)
- src/time/lamport.py         (LamportClock, VectorClock, MessageOrdering)
- src/demos/time_sync_demo.py (CLI demo of clocks/sync/reordering)
- tests/test_time.py          (unit + basic integration tests)

Notes:
- Uses a simple TCP protocol: TIME_SYNC request/response for SNTP-style offset.
- BoundedReordering buffers by timestamp with a max delay window.
- Logical time support via Lamport and vector clocks for causal reasoning.
