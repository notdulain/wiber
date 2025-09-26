def test_history_sorted_by_offset():
    from src.api import broker
    broker._storage.clear(); broker._next_offset.clear()

    msgs = [
        {"topic":"t","id":"a","from":"x","to":"y","text":"1","ts":2000},
        {"topic":"t","id":"b","from":"x","to":"y","text":"2","ts":1000},
        {"topic":"t","id":"c","from":"x","to":"y","text":"3","ts":3000},
    ]
    for m in msgs:
        broker.append("t", m)

    hist = broker.get_history("t")
    assert [m["offset"] for m in hist] == [0,1,2]