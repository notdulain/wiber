import sys
from pathlib import Path


# Ensure src is importable
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


from config.cluster import load_cluster_config, ClusterConfig, NodeConfig  # noqa: E402


def test_load_default_cluster_yaml():
    cfg_path = str((ROOT / "config" / "cluster.yaml").resolve())
    cfg = load_cluster_config(cfg_path)

    assert isinstance(cfg, ClusterConfig)
    assert len(cfg.nodes) >= 1
    # Basic shape check on first node
    n0 = cfg.nodes[0]
    assert isinstance(n0, NodeConfig)
    assert isinstance(n0.id, str) and n0.id
    assert isinstance(n0.host, str) and n0.host
    assert isinstance(n0.port, int) and 0 < n0.port <= 65535


def test_duplicate_ids_rejected(tmp_path):
    dup_yaml = tmp_path / "cluster.yaml"
    dup_yaml.write_text(
        """
nodes:
  - id: n1
    host: 127.0.0.1
    port: 9001
  - id: n1
    host: 127.0.0.1
    port: 9002
        """.strip()
    )

    try:
        load_cluster_config(str(dup_yaml))
        assert False, "Expected ValueError for duplicate node ids"
    except ValueError as e:
        assert "Duplicate node id" in str(e)


def test_missing_required_field(tmp_path):
    bad_yaml = tmp_path / "cluster.yaml"
    bad_yaml.write_text(
        """
nodes:
  - id: n1
    host: 127.0.0.1
        """.strip()
    )

    try:
        load_cluster_config(str(bad_yaml))
        assert False, "Expected ValueError for missing port"
    except ValueError as e:
        assert "required field" in str(e)


