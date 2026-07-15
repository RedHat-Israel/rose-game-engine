from rose.telemetry.observer import CompositeObserver
from rose.telemetry.observer import NullObserver
from rose.telemetry.observer import TelemetryObserver
from rose.telemetry.sinks import InMemorySink


def test_null_observer_is_a_noop():
    observer = NullObserver()

    # None of these should raise, regardless of arguments.
    observer.on_game_start(track=None, players=None)
    observer.on_step(step_index=0, players=None, track=None)
    observer.on_game_end(players=None, result=None)


def test_in_memory_sink_records_game_lifecycle():
    sink = InMemorySink()

    class FakePlayer:
        def __init__(self, name, score):
            self.name = name
            self.score = score

        def state(self):
            return {"name": self.name, "score": self.score}

    class FakeTrack:
        def state(self):
            return []

    players = [FakePlayer("A", 0), FakePlayer("B", 0)]
    track = FakeTrack()

    sink.on_game_start(track, players, {"track_type": "same"})
    sink.on_step(0, players, track)
    sink.on_step(1, players, track)
    result = {"scores": {"A": 10, "B": 5}, "winner": "A"}
    sink.on_game_end(players, result)

    assert len(sink.games) == 1
    game = sink.games[0]
    assert game["meta"] == {"track_type": "same"}
    assert len(game["steps"]) == 2
    assert game["steps"][0]["step"] == 0
    assert game["result"] == result


def test_in_memory_sink_tracks_multiple_games_independently():
    sink = InMemorySink()

    sink.on_game_start(track=None, players=[])
    sink.on_game_end(players=[], result={"scores": {}, "winner": None})

    sink.on_game_start(track=None, players=[])
    sink.on_game_end(players=[], result={"scores": {}, "winner": None})

    assert len(sink.games) == 2


def test_composite_observer_fans_out_to_children():
    calls = []

    class RecordingObserver(TelemetryObserver):
        def __init__(self, tag):
            self.tag = tag

        def on_step(self, step_index, players, track):
            calls.append((self.tag, step_index))

    composite = CompositeObserver([RecordingObserver("a"), RecordingObserver("b")])
    composite.on_step(3, players=None, track=None)

    assert calls == [("a", 3), ("b", 3)]
