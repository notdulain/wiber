from src.time.lamport import LamportClock


def test_lamport_tick_and_update():
    c = LamportClock()
    assert c.tick() == 1
    assert c.update(5) == 6
    assert c.tick() == 7

