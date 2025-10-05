from src.cluster.rpc import RpcMessage, JsonlCodec


def test_jsonl_codec_encode_decode_single():
    msg = RpcMessage(type="heartbeat", sender="n1", term=0, payload={"ts": 123.4})
    data = JsonlCodec.encode(msg)
    out = JsonlCodec.decode_lines(data)
    assert len(out) == 1
    m = out[0]
    assert m.type == "heartbeat"
    assert m.sender == "n1"
    assert m.term == 0
    assert m.payload["ts"] == 123.4


def test_jsonl_codec_decode_multiple_lines():
    msgs = [
        RpcMessage(type="heartbeat", sender="n1", term=0, payload={"ts": 1}),
        RpcMessage(type="heartbeat", sender="n2", term=0, payload={"ts": 2}),
    ]
    data = b"".join(JsonlCodec.encode(m) for m in msgs)
    out = JsonlCodec.decode_lines(data)
    assert [m.sender for m in out] == ["n1", "n2"]

