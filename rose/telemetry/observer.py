"""Telemetry observer interface for the game engine.

An observer is notified at well-defined points in the game lifecycle
(game start, each tick, game end). It is purely additive: nothing in
the engine requires an observer to be present, and the default
NullObserver is a no-op so existing call sites are unaffected.
"""


class TelemetryObserver(object):
    """Base class for telemetry observers. Override any subset of hooks."""

    def on_game_start(self, track, players, meta=None):
        """Called once, right after players/track are initialized.

        Args:
            track (Track): the initialized game track.
            players (list of Player): the initialized players.
            meta (dict, optional): extra context (e.g. track_type).
        """

    def on_step(self, step_index, players, track):
        """Called once per tick, right after score.process() has run.

        Args:
            step_index (int): 0-based tick counter for this game.
            players (list of Player): players with up-to-date state.
            track (Track): track with up-to-date state.
        """

    def on_game_end(self, players, result):
        """Called once, after the last tick of a game.

        Args:
            players (list of Player): players in their final state.
            result (dict): {"scores": {name: score}, "winner": name_or_None}.
        """


class NullObserver(TelemetryObserver):
    """No-op observer, used as the implicit default everywhere."""


class CompositeObserver(TelemetryObserver):
    """Fans out every hook to a list of child observers."""

    def __init__(self, observers):
        self._observers = list(observers)

    def on_game_start(self, track, players, meta=None):
        for observer in self._observers:
            observer.on_game_start(track, players, meta)

    def on_step(self, step_index, players, track):
        for observer in self._observers:
            observer.on_step(step_index, players, track)

    def on_game_end(self, players, result):
        for observer in self._observers:
            observer.on_game_end(players, result)
