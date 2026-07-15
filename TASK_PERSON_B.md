# Task: Collision/elimination handling + driver-side dodge logic for "grandma"

## Context

We're adding a new obstacle, `grandma` (see `rose-game-engine/TASK_PERSON_A.md` for how she spawns and moves — you don't need to touch that code, just consume the `obstacles.GRANDMA` constant she's adding).

Unlike every other obstacle, hitting grandma doesn't just cost points — it **eliminates the player**. In a 2-player match, only the player who crashed is knocked out; the engine stops polling their driver and stops moving/scoring them, while the other player keeps playing until `timeleft` runs out. Dodging her (steering `LEFT`/`RIGHT` away from her current column) needs no special code — the engine already moves the player's `x` before checking what obstacle they're standing on, exactly like the existing trash/bike/barrier hazards.

This task has two parts across two repos: the engine-side elimination logic (Part 1, `rose-game-engine`), and updating the example AI drivers so they actually dodge her (Part 2, `rose-game-ai`). Do Part 1 first — Part 2 is quick and just needs the constant name.

**Dependency:** you need `obstacles.GRANDMA` to exist (Person A adds it in `rose-game-engine/rose/common/obstacles.py`) before your `score.py` branch will import correctly. Everything else here is independent of their `track.py` internals.

## Part 1 — Engine: collision, elimination, game loop

Repo: `rose-game-engine`

### 1. Add an `eliminated` flag to `Player`

File: `rose/engine/player.py`

- In `__init__`, add: `self.eliminated = None`
- In `reset()`, add: `self.eliminated = False`
- In `state()`, add `"eliminated": self.eliminated` to the returned dict (so the UI/websocket clients can see it).

### 2. Handle the collision in `score.process()`

File: `rose/engine/score.py`

Add a guard at the very top of **both** loops so eliminated players stop participating entirely:
- Top of the `LEFT`/`RIGHT` handling loop (~line 23):
  ```python
  for player in players:
      if player.eliminated:
          continue
      ...
  ```
- Top of the main per-player obstacle loop (~line 54):
  ```python
  for player in sorted_players:
      if player.eliminated:
          continue
      ...
  ```

Then add a new `elif` branch next to the existing `TRASH`/`BIKE`/`BARRIER` one (~line 67):
```python
elif obstacle == obstacles.GRANDMA:
    # Player crashed into grandma: eliminated, out for the rest of the match.
    track.clear(player.x, player.y)
    player.score += config.score_move_backward
    player.hits += 1
    player.eliminated = True
```

This mirrors the existing "hit" penalty (same score/hits bookkeeping as trash/bike/barrier) but additionally flips `eliminated`. No new action constant is needed in `rose/common/actions.py` — dodging already works because `player.x` is updated by the `LEFT`/`RIGHT` branch earlier in `process()`, before this obstacle lookup runs.

### 3. Stop polling eliminated players

File: `rose/engine/net.py`

In `fetch_drivers_actions`, filter out eliminated players so the engine doesn't keep POSTing to a driver whose player already crashed:
```python
async def fetch_drivers_actions(players, track_matrix):
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            *(fetch_driver_action(session, player, track_matrix)
              for player in players if not player.eliminated),
            return_exceptions=True,
        )
```

### 4. Tests

File: `rose/engine/test_player.py`
- `test_player_state()` does an **exact dict-equality** assert (`assert player1.state() == expected_state`). Add `"eliminated": False` to `expected_state`, or this test will fail as soon as you add the field.

File: `rose/engine/test_score.py`
Add a new class, following the existing `TurnTest`/`SinglePlayerTest` pattern already in this file:
```python
class TestGrandma(SinglePlayerTest):
    obstacle = obstacles.GRANDMA

    def test_right(self):
        self.player.action = actions.RIGHT
        self.process()
        self.assert_move_right()
        self.assert_keep_obstacle()
        assert not self.player.eliminated

    def test_left(self):
        self.player.action = actions.LEFT
        self.process()
        self.assert_move_left()
        self.assert_keep_obstacle()
        assert not self.player.eliminated

    @pytest.mark.parametrize("action", FORWARD_ACTIONS)
    def test_other(self, action):
        self.player.action = action
        self.process()
        self.assert_move_back_no_punish()
        self.assert_remove_obstacle()
        assert self.player.eliminated
```

Also consider a small test (in `test_score.py` or a new `test_net.py`) confirming `fetch_drivers_actions` skips a player with `eliminated = True`.

### Verify Part 1

```bash
cd rose-game-engine
python -m pytest rose/engine/test_score.py rose/engine/test_player.py -v
```

## Part 2 — Driver-side: make the example drivers dodge her

Repo: `rose-game-ai` (a separate repo/checkout from Part 1 — not a folder inside `rose-game-engine`)

This repo doesn't run any collision/spawn logic — it's the AI client that receives the track grid over HTTP and decides an action. It just needs to recognize `"grandma"` and know to dodge her.

### 1. Mirror the obstacle constant

File: `rose/common/obstacles.py`

Add:
```python
GRANDMA = "grandma"
```

Do **not** add it to the `ALL` tuple here either, matching the engine's copy — `ALL` feeds this repo's own local `get_random_obstacle()`, used only for examples/tests, and keeping it out keeps both repos' vocabularies consistent.

### 2. Update the example drivers to dodge her

Treat `GRANDMA` as a "must dodge or die" hazard — same severity class as `TRASH`/`BIKE`/`BARRIER`, since getting it wrong ends the game instead of just costing points.

`mydriver.py` — add to both dicts:
```python
FORWARD_SCORES = {
    ...
    obstacles.GRANDMA: -10,
}
SIDESTEP_SCORES = {
    ...
    obstacles.GRANDMA: -10,
}
```

`mydriver2.py` — add to both dicts:
```python
FORWARD_REWARD = {
    ...
    obstacles.GRANDMA: -100,
}
SIDE_REWARD = {
    ...
    obstacles.GRANDMA: 0,
}
```

`examples/driver.py` — no code change needed. Its `else` branch already dodges any obstacle it doesn't explicitly recognize.

### 3. Document it

File: `examples/README.md`

Add a bullet in the obstacle list (same format as the existing `TRASH`/`BIKE`/`BARRIER` entries):
```
* `obstacles.GRANDMA`   you must return `actions.RIGHT` or `actions.LEFT` to bypass
                        her. Unlike other obstacles, hitting her ends the
                        game for your driver — it is not just a score penalty.
                        She also moves left/right on her own each turn, so
                        track her position every frame rather than assuming
                        she stays in the same lane.
```

### Verify Part 2

```bash
cd rose-game-ai
python -m pytest -v
```

## Handoff

Once your `player.eliminated` field and `score.py` branch (Part 1) are in, Person C (rendering in `rose-game-web-ui`) can wire up the game-over visual using the `eliminated` field now present in the broadcast player state. Manual smoke test at the end: run the engine with `mydriver.py`/`mydriver2.py`, force a collision, confirm `eliminated: true` shows up in the broadcast player state, that driver stops receiving POSTs, and the drivers actually dodge her in normal play.
