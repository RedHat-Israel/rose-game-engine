"""Headless batch simulation.

Runs full games against real rose-game-ai driver HTTP servers (the same
GET/POST contract used by the live engine, see rose.engine.net), but without
websockets and without the wall-clock throttle used by the live game loop, so
games run back-to-back as fast as the drivers respond. Useful for automated
evaluation of drivers (e.g. CI, tournaments) and for feeding a telemetry sink.
"""

import logging
import time

from rose.engine import config
from rose.engine import logic
from rose.engine.track import Track

log = logging.getLogger("simulate")


async def run_single_game(drivers, track_type, telemetry=None):
    """
    Play one full headless game between the given drivers.

    Args:
        drivers (list of str): driver URLs, one per player.
        track_type (str): "same" or "random", see Track.
        telemetry (TelemetryObserver, optional): observer notified per tick.

    Returns:
        dict: {"scores": {driver_name: score, ...}, "winner": name_or_None,
            "players": {driver_name: Player.state(), ...},
            "duration_seconds": float}.

    Raises:
        RuntimeError: if any driver failed to respond during initialization.
    """
    track = Track(track_type != "same")
    track.reset()

    players = await logic.initialize_players(drivers)
    if len(players) != len(drivers):
        raise RuntimeError(
            f"Only {len(players)}/{len(drivers)} drivers responded to initialization"
        )

    if telemetry is not None:
        telemetry.on_game_start(track, players, {"track_type": track_type})

    started_at = time.monotonic()
    for step_index in range(config.game_duration):
        await logic.play_tick(players, track, telemetry, step_index)

    result = {
        "scores": {player.name: player.score for player in players},
        "winner": logic.determine_winner(players),
        "players": {player.name: player.state() for player in players},
        "duration_seconds": round(time.monotonic() - started_at, 2),
    }

    if telemetry is not None:
        telemetry.on_game_end(players, result)

    return result


async def run_batch(drivers, games, track_type, telemetry=None):
    """
    Play `games` consecutive headless games between the given drivers and
    aggregate win/loss/tie stats per driver.

    Games run sequentially: rose-game-ai's reference server is a blocking
    socketserver.TCPServer, so concurrent games would just queue on it anyway.

    Returns:
        dict: aggregated stats, see rose.engine.simulate module docstring
            for shape, or the README for an example.
    """
    per_game = []
    for game_index in range(games):
        result = await run_single_game(drivers, track_type, telemetry)
        per_game.append(result)
        log.info("game %d/%d: %s", game_index + 1, games, result)

    return _aggregate(drivers, games, track_type, per_game)


def _aggregate(drivers, games, track_type, per_game):
    names = sorted({name for result in per_game for name in result["scores"]})
    results = {
        name: {"wins": 0, "losses": 0, "ties": 0, "avg_score": 0.0} for name in names
    }

    for result in per_game:
        winner = result["winner"]
        for name, score in result["scores"].items():
            results[name]["avg_score"] += score
            if winner is None:
                results[name]["ties"] += 1
            elif name == winner:
                results[name]["wins"] += 1
            else:
                results[name]["losses"] += 1

    for name in names:
        if games:
            results[name]["avg_score"] = round(results[name]["avg_score"] / games, 2)

    return {
        "games": games,
        "track_type": track_type,
        "drivers": list(drivers),
        "results": results,
        "per_game": per_game,
    }
