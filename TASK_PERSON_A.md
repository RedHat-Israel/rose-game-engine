# Task: Track mechanics for the "grandma" obstacle

## Context

We're adding a new obstacle, `grandma`, that moves side to side across the road as it scrolls toward the player (unlike every existing obstacle, which sits in one fixed column once generated). She spawns exactly twice per game: once at a random tick between frame 5 and 30, and once at a random tick between frame 31 and the end of the game. Her row must otherwise stay empty so her lateral movement never collides with a normal static obstacle.

This is the core mechanic: everything else (collision handling, driver logic) builds on top of what you produce here.

Design: instead of tracking a live obstacle object and mutating it reactively, **precompute her entire bounce trajectory once at spawn time** — a fixed list of 9 columns, one per depth she'll occupy over her lifetime. Each tick then becomes a simple lookup + `set`/`clear`, with no object-identity tracking needed.

Repo: `rose-game-engine`

## Steps

### 1. Add the obstacle constant

File: `rose/common/obstacles.py`

Add:
```python
GRANDMA = "grandma"
```

**Do not** add it to the `ALL` tuple. `ALL` feeds `get_random_obstacle()`, the uniform-random per-row picker used by `_generate_row()`. Grandma's spawn timing must be fully controlled by your new logic below, not the random picker — if she's in `ALL` she'll also spawn randomly and uncontrollably every tick.

### 2. Add spawn window config

File: `rose/engine/config.py`

Add:
```python
grandma_spawn_window_1 = (5, 30)
grandma_spawn_window_2_start = 31   # window 2 end = game_duration
```

### 3. Rewrite `Track` to support her

File: `rose/engine/track.py`

**`reset()`** — add:
```python
self._tick = 0
self._active_grandmas = []
self._pending_spawns = sorted([
    random.randint(*config.grandma_spawn_window_1),
    random.randint(config.grandma_spawn_window_2_start, config.game_duration),
])
```

**New helper `_spawn_grandma_row()`** — picks a random start column and direction, then precomputes the full 9-column path up front:
```python
def _spawn_grandma_row(self):
    row = [obstacles.NONE] * config.matrix_width
    col = random.randrange(config.matrix_width)
    direction = random.choice((-1, 1))
    path = [col]
    for _ in range(config.matrix_height - 1):
        if col + direction < 0 or col + direction >= config.matrix_width:
            direction *= -1
        col += direction
        path.append(col)
    row[path[0]] = obstacles.GRANDMA
    return row, path
```

**`update()`** — rewrite to:
```python
def update(self):
    self._tick += 1
    self._matrix.pop()

    still_active = []
    for grandma in self._active_grandmas:
        grandma["age"] += 1
        if grandma["age"] < config.matrix_height:
            old_col = grandma["path"][grandma["age"] - 1]
            new_col = grandma["path"][grandma["age"]]
            self.clear(old_col, grandma["age"])
            self.set(new_col, grandma["age"], obstacles.GRANDMA)
            still_active.append(grandma)
        # else: she scrolled past the last row and was just popped — drop her
    self._active_grandmas = still_active

    if self._pending_spawns and self._pending_spawns[0] == self._tick:
        self._pending_spawns.pop(0)
        row, path = self._spawn_grandma_row()
        self._active_grandmas.append({"path": path, "age": 0})
        self._matrix.insert(0, row)
    else:
        self._matrix.insert(0, self._generate_row())
```

Why this works: rows shift depth automatically via `pop()` + `insert(0, ...)` (an existing row's *content* doesn't change, only its index). So the cell you wrote for grandma last tick is still sitting at the *new* depth this tick — you just need to clear the stale column and set the new one, using the precomputed path as your only source of truth. No need to search the matrix or track object references.

### 4. Tests

File: `rose/engine/test_obstacles.py`
- Assert `obstacles.GRANDMA == "grandma"`.
- Assert `obstacles.GRANDMA not in obstacles.ALL`.

New file: `rose/engine/test_track.py` (doesn't exist yet — you're creating it):
- A grandma spawns at some tick within `[5, 30]` and another within `[31, config.game_duration]` over the course of a game.
- Her column changes by exactly 1 each tick she's active.
- She reverses direction instead of leaving `[0, matrix_width - 1]`.
- She's dropped from tracking once her `age` exceeds `matrix_height - 1` (i.e., she's scrolled off).
- Her row has no other obstacle in it at spawn time.

## Verify

```bash
cd rose-game-engine
python -m pytest rose/engine/test_track.py rose/engine/test_obstacles.py -v
```

## Handoff

Once `obstacles.GRANDMA` is merged, Person B (collision/elimination in this repo, plus driver-side dodge logic in `rose-game-ai`) and Person C (rendering in `rose-game-web-ui`) can both proceed — they only depend on the constant name `"grandma"`, not your `Track` internals.

Note for Person C: the `track` state broadcast to the browser already includes each obstacle's live `x`/`y` every tick (see `Track.state()`), so grandma's moving column requires no special handling on the rendering side beyond registering her sprite — the existing per-tick full repaint picks up her new position automatically.
