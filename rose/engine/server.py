import asyncio
import json
import logging
import uuid

import aiohttp
from aiohttp import web

from rose.engine import config
from rose.engine import logic
from rose.engine import simulate
from rose.telemetry.sinks import LiveSink

log = logging.getLogger("server")

# Global active_websockets
# IMPORTANT - shared with game loop in game.py
active_websockets = set()

# Global state
# IMPORTANT - shared with game loop in game.py
state = {"rate": None, "running": None, "reset": None, "drivers": [], "timeleft": None}

# Global telemetry sink, fed by the game loop, read by the /telemetry route.
telemetry = LiveSink()

# Global batch-simulation jobs, keyed by job id.
# {"status": "running" | "done" | "error", "result": dict or None, "error": str or None}
simulation_jobs = {}


async def admin_handler(request):
    """
    Handle admin requests to set the game rate.

    Args:
        request (aiohttp.web.Request): The request object.

    Returns:
        aiohttp.web.Response: A response indicating the new game rate or an error message.
    """
    rate = request.rel_url.query.get("rate")
    if rate:
        try:
            state["rate"] = float(rate)
        except ValueError:
            return web.Response(text="Invalid rate provided", status=400)

    running = request.rel_url.query.get("running")
    if running:
        try:
            state["running"] = int(running)
        except ValueError:
            return web.Response(text="Invalid running provided", status=400)

    reset = request.rel_url.query.get("reset")
    if reset:
        try:
            state["reset"] = int(reset)
        except ValueError:
            return web.Response(text="Invalid reset provided", status=400)
        # Stop the game on reset, unless this same request also asked to run
        # (formerly done as a side effect inside initialize_game(), which
        # raced with a Run request issued shortly after Reset).
        if running is None:
            state["running"] = 0

    # This expects the drivers to be passed as a comma-separated list in the query param
    # e.g., ?drivers=http://localhost:8081/drv2,http://driver.com:8090/
    drivers = request.rel_url.query.get("drivers")
    if drivers:
        drivers_list = drivers.split(",")
        state["drivers"] = drivers_list
        state["running"] = 0
        state["reset"] = 1

    return web.Response(text=json.dumps(state))


def _telemetry_snapshot():
    snapshot = telemetry.snapshot()
    snapshot["running"] = bool(state.get("running"))
    return snapshot


async def telemetry_handler(request):
    """Return recent per-tick history and recently finished game results."""
    return web.json_response(_telemetry_snapshot())


async def telemetry_clear_handler(request):
    """Clear the displayed tick log and match history."""
    telemetry.clear()
    return web.json_response(_telemetry_snapshot())


async def simulate_start_handler(request):
    """
    Start a batch simulation as a background job. Each round is driven
    through the same shared game state/websockets as manual play, so it
    plays out live on the main game screen, same as a human clicking
    Reset then Run would see, one round after another.

    Expected POST JSON body:
        {"drivers": [url1, url2], "games": <int>, "track": "same"|"random"}

    Returns:
        {"job_id": <str>} with status 202, so the caller can poll
        GET /simulate/{job_id} for progress/results.
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return web.Response(text="Invalid JSON body", status=400)

    drivers = payload.get("drivers")
    if not isinstance(drivers, list) or len(drivers) != 2:
        return web.Response(text="Exactly 2 driver URLs are required", status=400)

    try:
        games = int(payload.get("games", 10))
    except (TypeError, ValueError):
        return web.Response(text="Invalid games value", status=400)

    track_type = payload.get("track", "random")
    if track_type not in ("same", "random"):
        return web.Response(text="track must be 'same' or 'random'", status=400)

    job_id = uuid.uuid4().hex
    simulation_jobs[job_id] = {"status": "running", "result": None, "error": None}
    asyncio.create_task(_run_simulation_job(job_id, drivers, games, track_type))

    return web.json_response({"job_id": job_id}, status=202)


ROUND_POLL_INTERVAL_S = 0.2
INTER_ROUND_PAUSE_S = 2


async def _run_live_batch(drivers, games, track_type):
    """
    Play `games` rounds back-to-back through the shared live game loop, so
    each one is visible on the main game screen (same state/websockets a
    human's Reset+Run drives), and collect their results as they finish.

    Relies on the game loop's own reset/running handling (see
    logic.game_loop / logic.initialize_game): setting reset=1 and running=1
    together starts a fresh round immediately, and telemetry.on_game_end
    fires once it's done, which is what we poll for below.
    """
    per_game = []
    for game_index in range(games):
        finished_before = telemetry.result_count()

        state["drivers"] = list(drivers)
        state["track_type"] = track_type
        state["reset"] = 1
        state["running"] = 1

        while telemetry.result_count() == finished_before:
            await asyncio.sleep(ROUND_POLL_INTERVAL_S)

        result = telemetry.latest_result()
        per_game.append(result)
        log.info("live batch game %d/%d: %s", game_index + 1, games, result)

        if game_index < games - 1:
            await asyncio.sleep(INTER_ROUND_PAUSE_S)

    return simulate._aggregate(drivers, games, track_type, per_game)


async def _run_simulation_job(job_id, drivers, games, track_type):
    """Run a batch simulation and store its outcome for simulate_status_handler."""
    try:
        result = await _run_live_batch(drivers, games, track_type)
        simulation_jobs[job_id] = {"status": "done", "result": result, "error": None}
    except Exception as e:
        simulation_jobs[job_id] = {"status": "error", "result": None, "error": str(e)}


async def simulate_status_handler(request):
    """Return the status/result of a batch-simulation job started via POST /simulate."""
    job = simulation_jobs.get(request.match_info["job_id"])
    if job is None:
        return web.Response(text="Unknown job id", status=404)

    return web.json_response(job)


async def websocket_handler(request):
    """
    Handle WebSocket connections, echoing received messages with a prefix.

    Args:
        request (aiohttp.web.Request): The request object.

    Returns:
        aiohttp.web.WebSocketResponse: The WebSocket response object.
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    active_websockets.add(ws)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                response_message = f"Received: {msg.data}"
                await ws.send_str(response_message)
            elif msg.type == web.WSMsgType.ERROR:
                print(f"WebSocket error: {ws.exception()}")
    finally:
        active_websockets.remove(ws)
        await ws.close()

    return ws


async def run(
    http_port,
    listen_address,
    initial_rate,
    initial_running,
    initial_drivers,
    track_type,
):
    """
    Start the servers (HTTP and Websocket) and the game loop.

    Args:
        http_port (int): The port to listen on for the HTTP server.
        ws_port (int): The port to listen on for the Websocket server.
        listen_address (str): The address for both servers to bind to.
        initial_rate (float): The initial game rate in seconds.
        running (bollean): The initial starting state of the game.
        drivers (list of strings): list of driver URLs to use.
        public (str): Path to the static files directory.
        theme (str): Path to the static them resources directory.
        track_type (str): Type of track can be "random" or "same".
    """
    state["rate"] = initial_rate
    state["running"] = 1 if initial_running else 0
    state["drivers"] = initial_drivers
    state["timeleft"] = config.game_duration
    state["track_type"] = track_type

    app = web.Application()

    # Add application routes
    app.router.add_get("/ws", websocket_handler)
    app.router.add_post("/admin", admin_handler)
    app.router.add_get("/telemetry", telemetry_handler)
    app.router.add_post("/telemetry/clear", telemetry_clear_handler)
    app.router.add_post("/simulate", simulate_start_handler)
    app.router.add_get("/simulate/{job_id}", simulate_status_handler)

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, listen_address, http_port)

    # Start HTTP server
    await site.start()

    print(f"Track         {track_type}")
    print(f"Drivers       {initial_drivers}")
    print(f"Listen        {listen_address}:{http_port}")
    print(f"Server URL    http://127.0.0.1:{http_port}")

    # Start game loop
    # IMPORTANT: state and active_websockets are references, changes in this file will affect the game loop.
    await logic.game_loop(state, active_websockets, telemetry)
