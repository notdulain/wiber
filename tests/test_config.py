from textwrap import dedent
import tempfile
from src.config.cluster import load_cluster_config


def test_minimal_yaml_parsing_and_leader_choice():
    content = dedent(
        """
        nodes:
          - id: a
            host: 127.0.0.1
            port: 9001
          - id: b
            host: 127.0.0.1
            port: 9002
        """
    ).strip()
    with tempfile.NamedTemporaryFile("w+", suffix=".yaml") as tf:
        tf.write(content)
        tf.flush()
        cfg = load_cluster_config(tf.name)
    assert [n.id for n in cfg.nodes] == ["a", "b"]
    assert cfg.leader_id == "a"


def test_explicit_leader_id_override():
    content = dedent(
        """
        leader_id: b
        nodes:
          - id: a
            host: 127.0.0.1
            port: 9001
          - id: b
            host: 127.0.0.1
            port: 9002
        """
    ).strip()
    with tempfile.NamedTemporaryFile("w+", suffix=".yaml") as tf:
        tf.write(content)
        tf.flush()
        cfg = load_cluster_config(tf.name)
    assert cfg.leader_id == "b"

