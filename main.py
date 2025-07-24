import argparse
import asyncio
from http.server import HTTPServer
import logging
import os
import threading

from fileRecieverServer import FileRecieverServer
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

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        server.run(
            args.port,
            args.listen,
            args.initial_rate,
            args.running,
            args.drivers,
            args.track,
        )
    )


def startServer():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, FileRecieverServer)
    print("Serving on http://localhost:8000")
    httpd.serve_forever()


def deleteCustomMap():
    if os.path.exists("map/custom_map.csv"):
        os.remove("map/custom_map.csv")
    if os.path.exists("map/disabled_custom_map.csv"):
        os.remove("map/disabled_custom_map.csv")

if __name__ == "__main__":
    
    threading.Thread(target=startServer,daemon=True).start()
    try:
        main()
    finally:
        try:
            deleteCustomMap()    
        except FileNotFoundError:
            print("No custom map files to remove.")


