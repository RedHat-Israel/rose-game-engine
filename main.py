import argparse
import asyncio
import logging

from rose.engine import server


def main():
    parser = argparse.ArgumentParser(description="Start the game engine.")
    parser.add_argument(
        "-p", "--port", type=int, default=8880, help="Port for HTTP server"
    )
    parser.add_argument(
        "--listen", default="127.0.0.1", help="Listening address for servers"
    )
    parser.add_argument(
        "--initial-rate", type=float, default=1.0, help="Initial game rate in seconds"
    )
    parser.add_argument(
        "-d",
        "--drivers",
        nargs="+",
        help="List of driver URLs for the game engine to use",
    )
    parser.add_argument(
        "--running",
        action="store_true",
        help="Whether the game engine should start running immediately",
    )
    parser.add_argument(
        "-t",
        "--track",
        choices=["same", "random"],
        default="random",
        help="Choose the track type. Can be 'same' or 'random'.",
    )
    parser.add_argument(
        "--log", default="WARNING", help="Set the logging level. E.g. --log DEBUG"
    )

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log.upper()))

    asyncio.run(
        server.run(
            args.port,
            args.listen,
            args.initial_rate,
            args.running,
            args.drivers,
            args.track,
        )
    )


if __name__ == "__main__":
    main()
