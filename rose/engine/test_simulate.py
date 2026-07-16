import asyncio
import random

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from rose.common import actions
from rose.common import obstacles
from rose.engine import config
from rose.engine import simulate


def make_driver_app(name, action_fn):
    """A minimal stand-in for a rose-game-ai driver HTTP server."""

    async def get_handler(request):
        return web.json_response({"info": {"name": name}})

    async def post_handler(request):
        payload = await request.json()
        return web.json_response({"info": {"name": name, "action": action_fn(payload)}})

    app = web.Application()
    app.router.add_get("/", get_handler)
    app.router.add_post("/", post_handler)
    return app


class FakeDriver:
    """Runs a driver app on an ephemeral local port for the duration of a `with` block."""

    def __init__(self, name, action_fn):
        self._server = TestServer(make_driver_app(name, action_fn))

    async def __aenter__(self):
        await self._server.start_server()
        return str(self._server.make_url("/"))

    async def __aexit__(self, *exc_info):
        await self._server.close()


def test_run_single_game_ties_when_drivers_behave_identically(monkeypatch):
    monkeypatch.setattr(config, "game_duration", 6)

    async def scenario():
        async with FakeDriver(
            "DriverA", lambda payload: actions.NONE
        ) as url_a, FakeDriver("DriverB", lambda payload: actions.NONE) as url_b:
            return await simulate.run_single_game([url_a, url_b], track_type="same")

    result = asyncio.run(scenario())

    assert result["winner"] is None
    assert result["scores"]["DriverA"] == result["scores"]["DriverB"]


def test_run_single_game_determines_a_winner(monkeypatch):
    # Pin the obstacle stream so the outcome doesn't depend on real randomness:
    # every generated row is a CRACK placed exactly where both (stationary)
    # players sit in their lane.
    monkeypatch.setattr(config, "game_duration", 12)
    monkeypatch.setattr(obstacles, "get_random_obstacle", lambda: obstacles.CRACK)
    monkeypatch.setattr(random, "choice", lambda seq: 1)

    async def scenario():
        async with FakeDriver(
            "DriverA", lambda payload: actions.JUMP
        ) as url_a, FakeDriver("DriverB", lambda payload: actions.NONE) as url_b:
            return await simulate.run_single_game([url_a, url_b], track_type="same")

    result = asyncio.run(scenario())

    assert result["winner"] == "DriverA"
    assert result["scores"]["DriverA"] > result["scores"]["DriverB"]


def test_run_single_game_raises_if_a_driver_does_not_respond():
    async def scenario():
        async with FakeDriver("DriverA", lambda payload: actions.NONE) as url_a:
            return await simulate.run_single_game(
                [url_a, "http://127.0.0.1:1/unreachable"], track_type="same"
            )

    with pytest.raises(RuntimeError):
        asyncio.run(scenario())


def test_run_batch_aggregates_win_loss_tie_stats(monkeypatch):
    monkeypatch.setattr(config, "game_duration", 5)

    async def scenario():
        async with FakeDriver(
            "DriverA", lambda payload: actions.NONE
        ) as url_a, FakeDriver("DriverB", lambda payload: actions.NONE) as url_b:
            stats = await simulate.run_batch([url_a, url_b], games=3, track_type="same")
            return stats, url_a, url_b

    stats, url_a, url_b = asyncio.run(scenario())

    assert stats["games"] == 3
    assert stats["track_type"] == "same"
    assert stats["drivers"] == [url_a, url_b]
    assert len(stats["per_game"]) == 3

    for name in ("DriverA", "DriverB"):
        assert stats["results"][name]["ties"] == 3
        assert stats["results"][name]["wins"] == 0
        assert stats["results"][name]["losses"] == 0

    assert (
        stats["results"]["DriverA"]["avg_score"]
        == stats["results"]["DriverB"]["avg_score"]
    )
