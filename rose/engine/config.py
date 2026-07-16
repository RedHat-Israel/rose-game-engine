# config.py

# Default Configuration
drivers = []
run = "stop"

game_rate = 1.0
game_duration = 60

matrix_height = 9
matrix_width = 6

max_players = 2
cells_per_player = 3

score_move_forward = 10
score_move_backward = -10
score_pickup = 10
score_jump = 5
score_brake = 4

# Fuel
starting_fuel = 40
max_fuel = 60
fuel_per_move = 2
fuel_can_refill = 20
fuel_spawn_chance = 0.25
fuel_min_gap = 3  # rows a fuel can must wait after the previous one, so they spread out
