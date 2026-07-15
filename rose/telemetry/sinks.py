"""Concrete TelemetryObserver sinks."""

import collections
import json

from rose.telemetry.observer import TelemetryObserver


class InMemorySink(TelemetryObserver):
    """Keeps per-step snapshots and the final result in memory.

    Handy for batch simulation, where the run is over long before anyone
    could tail a file, and for tests.
    """

    def __init__(self):
        self.games = []
        self._current_game = None

    def on_game_start(self, track, players, meta=None):
        self._current_game = {
            "meta": meta or {},
            "steps": [],
            "result": None,
        }
        self.games.append(self._current_game)

    def on_step(self, step_index, players, track):
        self._current_game["steps"].append(
            {
                "step": step_index,
                "players": [player.state() for player in players],
                "track": track.state(),
            }
        )

    def on_game_end(self, players, result):
        self._current_game["result"] = result


class LiveSink(TelemetryObserver):
    """Keeps a bounded in-memory history for the live, running game server.

    Unlike InMemorySink, this isn't grouped per-game: it's a flat rolling log
    of recent ticks plus a rolling log of recently finished games, meant to be
    polled over HTTP (see rose.engine.server's `/telemetry` route) by a
    dashboard that just wants "what's been happening lately".
    """

    def __init__(self, max_ticks=500, max_results=20):
        self._history = collections.deque(maxlen=max_ticks)
        self._recent_results = collections.deque(maxlen=max_results)
        self._total_finished = 0
        # Snapshot of _total_finished as of the last clear(), subtracted out
        # for display so round numbering restarts at 1 after a clear, without
        # touching _total_finished itself (see result_count()/clear() below).
        self._round_offset = 0

    def on_step(self, step_index, players, track):
        self._history.append(
            {
                "step": step_index,
                "players": [player.state() for player in players],
            }
        )

    def on_game_end(self, players, result):
        self._recent_results.append(result)
        self._total_finished += 1

    def result_count(self):
        """Total number of finished games recorded so far (monotonic).

        Deliberately backed by a counter, not len(_recent_results) — that
        deque is capped at max_results, so its length would plateau and
        break callers polling for "has another game finished" past that cap.
        """
        return self._total_finished

    def latest_result(self):
        """Most recently finished game's result, or None if none yet."""
        return self._recent_results[-1] if self._recent_results else None

    def clear(self):
        """Clear the displayed tick log, match history, and round numbering.

        Deliberately leaves _total_finished itself untouched: it's used by
        server._run_live_batch to detect "has another round finished", and
        resetting it here would break any batch job in flight. Round
        numbering for display is reset instead via _round_offset (see
        snapshot()), so the next finished game shows as round 1 again
        without disturbing that internal counter.
        """
        self._history.clear()
        self._recent_results.clear()
        self._round_offset = self._total_finished

    def snapshot(self):
        """Return a JSON-serializable view of recent ticks and results."""
        return {
            "history": list(self._history),
            "recent_results": list(self._recent_results),
            "total_finished": self._total_finished - self._round_offset,
        }


class JSONLSink(TelemetryObserver):
    """Appends one JSON object per event to a file, one event per line.

    This is a natural feed for a future dashboard to tail (`tail -f` or a
    simple polling reader), without the dashboard needing to understand
    engine internals beyond the JSON shape written here.
    """

    def __init__(self, path):
        self._path = path

    def on_game_start(self, track, players, meta=None):
        self._append({"event": "game_start", "meta": meta or {}})

    def on_step(self, step_index, players, track):
        self._append(
            {
                "event": "step",
                "step": step_index,
                "players": [player.state() for player in players],
                "track": track.state(),
            }
        )

    def on_game_end(self, players, result):
        self._append({"event": "game_end", "result": result})

    def _append(self, record):
        with open(self._path, "a") as f:
            f.write(json.dumps(record) + "\n")
