""" Game obstacles """

import random

NONE = ""  # NOQA
CRACK = "crack"  # NOQA
TRASH = "trash"  # NOQA
PENGUIN = "penguin"  # NOQA
BIKE = "bike"  # NOQA
WATER = "water"  # NOQA
BARRIER = "barrier"  # NOQA
COIN = "coin"  # NOQA

ALL = (NONE, CRACK, TRASH, PENGUIN, BIKE, WATER, BARRIER, COIN)


def get_random_obstacle():
    return random.choice(ALL)
