""" Game obstacles """

import random

NONE = ""  # NOQA
CRACK = "crack"  # NOQA
TRASH = "trash"  # NOQA
PENGUIN = "penguin"  # NOQA
BIKE = "bike"  # NOQA
WATER = "water"  # NOQA
BARRIER = "barrier"  # NOQA
FUEL = "fuel"  # NOQA

# FUEL is not included: it is spawned by the track on its own schedule, not
# by get_random_obstacle().
ALL = (NONE, CRACK, TRASH, PENGUIN, BIKE, WATER, BARRIER)


def get_random_obstacle():
    return random.choice(ALL)
