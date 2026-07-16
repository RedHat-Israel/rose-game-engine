import argparse
import asyncio
import json
import logging

from rose.engine import simulate


def main():
    parser = argparse.ArgumentParser(
        description="Run headless batch simulations of the engine against rose-game-ai drivers."
    )
    parser.add_argument(
        "-d",
        "--drivers",
        nargs=2,
        required=True,
        metavar=("DRIVER1_URL", "DRIVER2_URL"),
        help="Exactly two driver URLs to simulate (matches the game's 2-player design).",
    )
    parser.add_argument(
        "-g", "--games", type=int, default=10, help="Number of games to simulate."
    )
    parser.add_argument(
        "-t",
        "--track",
        choices=["same", "random"],
        default="random",
        help="Choose the track type. Can be 'same' or 'random'.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="batch_stats.json",
        help="Path to write the aggregated JSON stats to.",
    )
    parser.add_argument(
        "--log", default="WARNING", help="Set the logging level. E.g. --log DEBUG"
    )

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log.upper()))

    stats = asyncio.run(simulate.run_batch(args.drivers, args.games, args.track))

    with open(args.output, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Simulated {args.games} games -> {args.output}")
    print(json.dumps(stats["results"], indent=2))


if __name__ == "__main__":
    main()
