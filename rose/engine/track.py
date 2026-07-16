import random

from rose.engine import config
from rose.common import obstacles


class Track(object):
    def __init__(self, is_track_random=False):
        self._matrix = None
        self.is_track_random = is_track_random
        self.reset()

    # Game state interface

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
        
    def state(self):
        """Return read only serialize-able state for sending to client"""
        items = []
        for y, row in enumerate(self._matrix):
            for x, obs in enumerate(row):
                if obs != obstacles.NONE:
                    items.append({"name": obs, "x": x, "y": y})
        return items

    def matrix(self):
        """Return the track matrix"""
        return self._matrix

    # Track interface

    def get(self, x, y):
        """Return the obstacle in position x, y"""
        return self._matrix[y][x]

    def set(self, x, y, obstacle):
        """Set obstacle in position x, y"""
        self._matrix[y][x] = obstacle

    def clear(self, x, y):
        """Clear obstacle in position x, y"""
        self._matrix[y][x] = obstacles.NONE

    def reset(self):
        self._matrix = [
            [obstacles.NONE] * config.matrix_width for x in range(config.matrix_height)
        ]

        self._tick = 0
        self._active_grandmas = []
        self._pending_spawns = sorted([
            random.randint(*config.grandma_spawn_window_1),
            random.randint(config.grandma_spawn_window_2_start, config.game_duration),
        ])

    # Private

    def _generate_row(self):
        """
        Generates new row with obstacles

        Try to create fair but random obstacle stream. Each player get the same
        obstacles, but in different cells if 'is_track_random' is True.
        Otherwise, the tracks will be identical.
        """

        # Create initial empty row
        row = [obstacles.NONE] * config.matrix_width

        # Get a random obstacle
        obstacle = obstacles.get_random_obstacle()

        if self.is_track_random:
            for lane in range(config.max_players):
                # Get a random cell for each player
                cell = random.choice(range(0, config.cells_per_player))

                row[cell + lane * config.cells_per_player] = obstacle
        else:
            # Get a random cell, and use it for all players
            cell = random.choice(range(0, config.cells_per_player))

            for lane in range(config.max_players):
                row[cell + lane * config.cells_per_player] = obstacle

        return row

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