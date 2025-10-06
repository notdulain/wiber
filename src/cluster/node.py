"""Node process entry and orchestration.

Responsibilities:
- Initialize consensus (Raft) and RPC server
- Start client-facing API (wire protocol)
- Manage replication log and dedup cache
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from typing import Optional, Dict, Set

from api.wire import create_api_server
from cluster.rpc import RpcServer, RpcClient
from cluster.raft import Raft
from replication.dedup import DedupCache
from replication.log import CommitLog
from src.time.sync import TimeSyncServer, TimeSyncClient, TimeSyncConfig
from src.time.lamport import MessageOrdering
from utils.logging_config import setup_logging


class Node:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 0, 
                 other_nodes: list = None, data_dir: str = ".data", startup_grace: float = 0.5):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.other_nodes = other_nodes or []  # List of (host, port) tuples
        self._api_server: Optional[asyncio.AbstractServer] = None
        self._rpc_server: Optional[RpcServer] = None
        self._raft: Optional[Raft] = None
        self._log = CommitLog(base_dir=data_dir)
        self._startup_grace = float(startup_grace)
        self._dedup = DedupCache(max_size=100)
        # topic -> set of StreamWriter subscribers (managed by wire.py)
        self._subs: Dict[str, Set[asyncio.StreamWriter]] = {}
        # time sync services
        self._timesync_server: Optional[TimeSyncServer] = None
        self._timesync_client: Optional[TimeSyncClient] = None
        self._timesync_task: Optional[asyncio.Task] = None
        self._timesync_port: Optional[int] = None
        self._ordering = MessageOrdering(self.node_id, use_vector_clocks=False)
        self._logger = setup_logging(level="INFO", node_id=self.node_id, component="node")
        self._metrics = Counter()

    def start(self) -> None:
        """Start node services (consensus, API, replication)."""
        try:
            asyncio.run(self._start_async())
        except KeyboardInterrupt:
            print(f"\nNode {self.node_id} shutting down...")

    async def _start_async(self) -> None:
        try:
            # Initialize Raft consensus
            self._raft = Raft(self.node_id, self.other_nodes)
            # Add a startup grace so peers have time to bring up RPC
            self._raft.set_startup_grace(self._startup_grace)
            # Provide API address hint to Raft for redirects
            self._raft.api_host = self.host
            self._raft.api_port = self.port
            
            # Provide RPC client factory to Raft
            self._raft.rpc_client_factory = lambda host, port, node_id: RpcClient(host, port, node_id)
            # Wire apply callback to durability (CommitLog)
            self._raft.set_apply_callback(self._apply_payload)
            # Configure Raft persistence under the node's data dir
            try:
                from pathlib import Path
                raft_dir = Path(getattr(self._log, 'base_path', Path('.data'))).parent / self.node_id / 'raft'
            except Exception:
                raft_dir = Path('data') / self.node_id / 'raft'
            self._raft.set_storage_dir(raft_dir)

            # Start time synchronization server on API port + 200
            self._timesync_port = None
            try:
                ts_port = self.port + 200
                self._timesync_server = TimeSyncServer(self.node_id, host=self.host, port=ts_port)
                self._timesync_server.start()
                self._timesync_client = TimeSyncClient(self.node_id, TimeSyncConfig())
                self._timesync_port = ts_port
            except Exception as e:
                print(f"TimeSyncServer start failed for {self.node_id}: {e}")

            # Start API server (for clients)
            self._api_server = await create_api_server(self.host, self.port, node=self)
            
            # Start RPC server (for other nodes) on port + 1000
            rpc_port = self.port + 1000
            self._rpc_server = RpcServer(self.host, rpc_port, self.node_id, self._raft, node=self)
            await self._rpc_server.start()
            # Mark RPC as ready (starts the grace countdown)
            self._raft.mark_rpc_ready()
            
            self._logger.info(
                "node_started",
                api=f"{self.host}:{self.port}",
                rpc=f"{self.host}:{rpc_port}",
                time_sync=f"{self.host}:{self._timesync_port}" if self._timesync_port else None,
                state=self._raft.state.value,
                term=self._raft.current_term,
            )
            
            # Run both servers concurrently with Raft ticking
            async with self._api_server:
                try:
                    await asyncio.gather(
                        self._api_server.serve_forever(),
                        self._raft_tick_loop(),
                        self._timesync_loop(),
                        self._metrics_loop()
                    )
                except asyncio.CancelledError:
                    pass
                finally:
                    if self._timesync_server:
                        try:
                            self._timesync_server.stop()
                        except Exception:
                            pass
        except OSError as e:
            if e.errno == 10048:  # Port already in use
                self._logger.error("port_in_use", port=self.port, node=self.node_id)
                raise
            else:
                raise

    async def _raft_tick_loop(self) -> None:
        """Raft consensus tick loop."""
        while True:
            if self._raft:
                self._raft.tick()
            await asyncio.sleep(0.01)  # Tick every 10ms

    async def _timesync_loop(self) -> None:
        """Background loop to keep time offsets updated."""
        if not self._timesync_client or not self._timesync_server:
            return
        await asyncio.sleep(0.5)  # allow peers to start
        peers = []
        for host, port in self.other_nodes:
            peers.append((host, port + 200, f"{host}:{port}"))
        try:
            while True:
                for host, port, peer_id in peers:
                    offset = self._timesync_client.measure_offset(host, port, peer_id)
                    self._logger.debug(
                        "timesync_measure",
                        peer=peer_id,
                        port=port,
                        offset=offset,
                    )
                    if offset is not None:
                        self._inc_metric("timesync_samples")
                    await asyncio.sleep(0.1)
                await asyncio.sleep(self._timesync_client.config.sync_interval)
        except asyncio.CancelledError:
            raise

    async def _metrics_loop(self) -> None:
        """Periodically emit metrics."""
        while True:
            try:
                snapshot = dict(self._metrics)
                raft_state = None
                match_index = None
                commit_index = None
                if self._raft:
                    raft_state = self._raft.state.value
                    commit_index = self._raft.commit_index
                    match_index = dict(self._raft.match_index)
                self._logger.info(
                    "metrics",
                    metrics=snapshot,
                    raft_state=raft_state,
                    commit_index=commit_index,
                    match_index=match_index,
                )
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break

    def _inc_metric(self, name: str, amount: int = 1) -> None:
        self._metrics[name] += amount

    async def ping_other_node(self, other_host: str, other_port: int) -> dict:
        """Ping another node via RPC."""
        rpc_port = other_port + 1000  # RPC is on port + 1000
        client = RpcClient(other_host, rpc_port, self.node_id)
        return await client.ping()

    # Apply committed payloads to durable commit log
    def _apply_payload(self, payload: dict) -> None:
        try:
            topic = payload.get("topic")
            mid = payload.get("id")
            ts = payload.get("ts")
            msg = payload.get("msg")
            if not (topic and mid is not None and ts is not None and msg is not None):
                return
            ordering_info = payload.pop("ordering_info", None)
            if ordering_info and getattr(self, "_ordering", None):
                try:
                    self._ordering.update_from_message(ordering_info)
                except Exception:
                    pass
            rec = self._log.append(
                topic,
                mid,
                float(ts),
                str(msg),
                corrected_ts=payload.get("corrected_ts"),
                logical_time=payload.get("logical_time"),
                clock_type=payload.get("clock_type"),
            )
            self._inc_metric("messages_applied")
            # Fan-out to live subscribers for this topic
            try:
                asyncio.get_event_loop().create_task(
                    self._broadcast_applied(topic, rec)
                )
            except RuntimeError:
                # No running loop (e.g., during teardown); skip broadcast
                pass
        except Exception:
            # Ignore apply failures here; production code should log
            pass

    def _annotate_payload(self, payload: Dict) -> Dict:
        data = dict(payload)
        ordering_info = None
        if getattr(self, "_ordering", None):
            try:
                ordering_info = self._ordering.create_timestamp()
            except Exception:
                ordering_info = None
        if ordering_info:
            data["logical_time"] = ordering_info.get("logical_time")
            data["clock_type"] = ordering_info.get("clock_type")
            data["ordering_info"] = ordering_info
            base_ts = ordering_info.get("timestamp", time.time())
        else:
            base_ts = time.time()
        offset = 0.0
        if self._timesync_client:
            try:
                offset = self._timesync_client.get_average_offset()
            except Exception:
                offset = 0.0
        data["ts"] = base_ts
        data["corrected_ts"] = base_ts + offset
        return data

    def _add_subscriber(self, topic: str, writer: asyncio.StreamWriter) -> None:
        self._subs.setdefault(topic, set()).add(writer)

    def _remove_writer(self, writer: asyncio.StreamWriter) -> None:
        for subs in self._subs.values():
            subs.discard(writer)

    async def _broadcast_applied(self, topic: str, rec: dict) -> None:
        ts = rec.get("ts")
        corrected = rec.get("corrected_ts", ts)
        logical = rec.get("logical_time")
        clock_type = rec.get("clock_type")
        prefix = (
            f"MSG {topic} {rec.get('id','')} {rec.get('offset',0)} {ts} {corrected} "
            f"{logical if logical is not None else '-'} {clock_type or '-'} "
        )
        line = prefix + str(rec.get('msg', '')) + "\n"
        dead: Set[asyncio.StreamWriter] = set()
        for w in list(self._subs.get(topic, set())):
            try:
                w.write(line.encode("utf-8"))
                await w.drain()
            except Exception:
                dead.add(w)
        for w in dead:
            self._remove_writer(w)
