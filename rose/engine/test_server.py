import asyncio

from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp.test_utils import TestServer

from rose.common import actions
from rose.engine import config
from rose.engine import server
from rose.telemetry.sinks import LiveSink


class FakePlayer:
    def __init__(self, name, score):
        self.name = name
        self.score = score

    def state(self):
        return {"name": self.name, "score": self.score}


def build_app():
    app = web.Application()
    app.router.add_get("/telemetry", server.telemetry_handler)
    app.router.add_post("/simulate", server.simulate_start_handler)
    app.router.add_get("/simulate/{job_id}", server.simulate_status_handler)
    return app


def make_driver_app(name, action_fn):
    async def get_handler(request):
        return web.json_response({"info": {"name": name}})

    async def post_handler(request):
        payload = await request.json()
        return web.json_response({"info": {"name": name, "action": action_fn(payload)}})

    driver_app = web.Application()
    driver_app.router.add_get("/", get_handler)
    driver_app.router.add_post("/", post_handler)
    return driver_app


class FakeDriver:
    def __init__(self, name, action_fn):
        self._server = TestServer(make_driver_app(name, action_fn))

    async def __aenter__(self):
        await self._server.start_server()
        return str(self._server.make_url("/"))

    async def __aexit__(self, *exc_info):
        await self._server.close()


def test_telemetry_handler_returns_recent_history_and_results(monkeypatch):
    sink = LiveSink()
    sink.on_step(0, [FakePlayer("A", 10), FakePlayer("B", 5)], track=None)
    sink.on_game_end(
        players=None, result={"scores": {"A": 100, "B": 90}, "winner": "A"}
    )
    monkeypatch.setattr(server, "telemetry", sink)

    async def scenario():
        async with TestClient(TestServer(build_app())) as client:
            resp = await client.get("/telemetry")
            return resp.status, await resp.json()

    status, body = asyncio.run(scenario())

    assert status == 200
    assert len(body["history"]) == 1
    assert body["history"][0]["players"] == [
        {"name": "A", "score": 10},
        {"name": "B", "score": 5},
    ]
    assert body["recent_results"] == [{"scores": {"A": 100, "B": 90}, "winner": "A"}]


def test_simulate_endpoint_rejects_bad_payloads():
    async def scenario():
        async with TestClient(TestServer(build_app())) as client:
            resp = await client.post("/simulate", json={"drivers": ["only-one"]})
            return resp.status

    assert asyncio.run(scenario()) == 400


def test_simulate_status_unknown_job_is_404():
    async def scenario():
        async with TestClient(TestServer(build_app())) as client:
            resp = await client.get("/simulate/does-not-exist")
            return resp.status

    assert asyncio.run(scenario()) == 404


def test_simulate_job_runs_in_background_and_completes(monkeypatch):
    monkeypatch.setattr(config, "game_duration", 4)

    async def scenario():
        async with FakeDriver(
            "DriverA", lambda payload: actions.NONE
        ) as url_a, FakeDriver(
            "DriverB", lambda payload: actions.NONE
        ) as url_b, TestClient(
            TestServer(build_app())
        ) as client:
            start_resp = await client.post(
                "/simulate",
                json={"drivers": [url_a, url_b], "games": 2, "track": "same"},
            )
            assert start_resp.status == 202
            job_id = (await start_resp.json())["job_id"]

            for _ in range(200):
                status_resp = await client.get(f"/simulate/{job_id}")
                body = await status_resp.json()
                if body["status"] != "running":
                    return body
                await asyncio.sleep(0.01)

            raise AssertionError("job never finished")

    job = asyncio.run(scenario())

    assert job["status"] == "done"
    assert job["result"]["games"] == 2
    assert set(job["result"]["results"].keys()) == {"DriverA", "DriverB"}
