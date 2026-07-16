import random

from rose.engine import config
from rose.engine import track
from rose.common import obstacles


def test_grandma_spawns_within_both_windows():
    t = track.Track()
    spawn1, spawn2 = t._pending_spawns

    assert config.grandma_spawn_window_1[0] <= spawn1 <= config.grandma_spawn_window_1[1]
    assert config.grandma_spawn_window_2_start <= spawn2 <= config.game_duration

    spawn_ticks = []
    for tick in range(1, config.game_duration + 1):
        before = len(t._active_grandmas)
        t.update()
        if len(t._active_grandmas) > before:
            spawn_ticks.append(tick)

    assert spawn_ticks == [spawn1, spawn2]


def test_grandma_column_changes_by_one_each_tick():
    t = track.Track()
    _, path = t._spawn_grandma_row()

    assert len(path) == config.matrix_height
    for previous_col, next_col in zip(path, path[1:]):
        assert abs(next_col - previous_col) == 1


def test_grandma_reverses_direction_at_boundary(monkeypatch):
    monkeypatch.setattr(random, "randrange", lambda n: 0)
    monkeypatch.setattr(random, "choice", lambda seq: -1)

    t = track.Track()
    _, path = t._spawn_grandma_row()

    assert path[0] == 0
    assert all(0 <= col <= config.matrix_width - 1 for col in path)
    # Direction would take her to -1 (out of bounds), so it reverses instead.
    assert path[1] == 1


def test_grandma_dropped_once_age_exceeds_matrix_height_minus_one():
    t = track.Track()
    t._pending_spawns = [1, config.game_duration + 1]

    t.update()  # Spawns on tick 1, age starts at 0.
    assert len(t._active_grandmas) == 1

    for _ in range(config.matrix_height - 1):
        t.update()
        assert len(t._active_grandmas) == 1

    t.update()  # Her age now exceeds matrix_height - 1.
    assert len(t._active_grandmas) == 0


def test_grandma_spawn_row_has_no_other_obstacles():
    t = track.Track()
    row, path = t._spawn_grandma_row()

    for x, obstacle in enumerate(row):
        if x == path[0]:
            assert obstacle == obstacles.GRANDMA
        else:
            assert obstacle == obstacles.NONE
