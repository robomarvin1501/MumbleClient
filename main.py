import argparse
import os
import keyboard
import json

from MumbleClient import Mumbler, check_configuration_update

cli_parser = argparse.ArgumentParser()

cli_parser.add_argument("server", help="The IP or computer name of the Mumble server.")
cli_parser.add_argument("nickname", help="The nickname of this user. Usually the name of the computer.")
cli_parser.add_argument("configuration_path", help="The path to the configuration file")
cli_parser.add_argument("--refresh_time", type=int,
                        help="How long in seconds to wait between refreshing the configuration file. Default is 10 seconds")

args = cli_parser.parse_args()

server = args.server
nickname = args.nickname
configuration_path = args.configuration_path
if args.refresh_time is None:
    refresh_time = 10
else:
    refresh_time = args.refresh_time

mumbler = Mumbler(server, nickname, configuration_path=configuration_path)
check_configuration_update(mumbler.mumble_client, configuration_path, os.path.getmtime(configuration_path), refresh_time)

mumbler.window.mainloop()

# keyboard.wait("esc")
print("Exited")
