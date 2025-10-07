Snapshot of Phase 2 (Raft election + RPC scaffolding) from branch 'sr_leader'.

How to apply later:
- From your new branch, copy files from this buffer path to the repo root, preserving paths.
- Or ask Codex to apply this buffer to the current branch.

Included files:
- requirements.txt
- config/cluster.yaml
- scripts/run_cluster.py
- src/api/wire.py
- src/cluster/node.py
- src/cluster/raft.py
- src/cluster/rpc.py
- src/config/cluster.py
- src/utils/logging_config.py
- src/utils/validation.py
- tests/test_api_ping.py
- tests/test_config.py
- tests/test_raft.py
- tests/test_rpc.py

Notes:
- src/config/cluster.py uses PyYAML (see requirements.txt).
- Raft AppendEntries is a placeholder; Phase 3 will add replication.
