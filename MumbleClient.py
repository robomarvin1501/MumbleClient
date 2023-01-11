import json
import sys
import os
import time
import keyboard
import pyaudio
import threading

import pymumble_py3
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED as PCS
from pymumble_py3.messages import MoveCmd

# Example mumble command
# self.mumble.commands.new_cmd(
#     cmds.ModUserState(
#         self.mumble.users.myself_session, {
#             "session": self.mumble.users.myself_session,
#             "listening_channel_add": self.mumble.channels.keys() ^ {0}
#         }
#     )
# )

# pyaudio constants
CHUNKSIZE = 1024
FORMAT = pyaudio.paInt16  # pymumble soundchunk.pcm is 16 bits
PYAUDIO_CHANNELS = 1
RATE = 48000  # pymumble soundchunk.pcm is 48000Hz


class MumbleClient:
    def __init__(self, server, nickname, pwd="", configuration=None):
        if configuration is None:
            raise Exception(f"Invalid configuration: {configuration}")

        self.pwd = pwd
        self.server = server
        self.nickname = nickname

        self.configuration = configuration

        self.mumble: pymumble_py3.Mumble = None  # Defined in _create_mumble_instance
        self.p: pyaudio.PyAudio = None  # Defined in _setup_audio
        self.stream: pyaudio.Stream = None  # Defined in _setup_audio

        self._setup_audio()
        self._create_mumble_instance()
        self._setup_keyboard_hooks()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

    def _create_mumble_instance(self):
        self.mumble = pymumble_py3.Mumble(self.server, self.nickname, password=self.pwd)
        self.mumble.callbacks.set_callback(PCS, self.sound_retriever_handler)
        self.mumble.set_receive_sound(1)
        self.mumble.start()
        self.mumble.is_ready()

    def _setup_audio(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=FORMAT,
                                  channels=PYAUDIO_CHANNELS,
                                  rate=RATE,
                                  input=True,
                                  output=True,
                                  frames_per_buffer=CHUNKSIZE)

    def _setup_keyboard_hooks(self):
        keyboard.add_hotkey(self.configuration["speak"], self.audio_capture)
        person_type = None

        for user_type in self.configuration["user_types"]:
            if self.nickname in self.configuration["user_types"][user_type]:
                person_type = user_type
                break

        if person_type is not None:
            for hook in self.configuration["configurations"][person_type]:
                keyboard.add_hotkey(hook[0], self.change_channel, args=(hook[1],))

    def update_configuration(self, configuration: dict):
        self.configuration = configuration

        keyboard.unhook_all()

        self._setup_keyboard_hooks()

    def change_channel(self, target_channel_name):
        self.mumble.execute_command(
            MoveCmd(self.mumble.users.myself_session,
                    self.mumble.channels.find_by_name(target_channel_name)["channel_id"]))

    def sound_retriever_handler(self, user, soundchunk):
        self.stream.write(soundchunk.pcm)

    def audio_capture(self):
        starting_time = time.time()
        while time.time() - starting_time < 1:
            data = self.stream.read(CHUNKSIZE, exception_on_overflow=False)
            self.mumble.sound_output.add_sound(data)


def check_configuration_update(mumble_client: MumbleClient, configuration_path: str, last_update_time: float,
                               refresh_time: int = 10):
    update_time = os.path.getmtime(configuration_path)
    if update_time > last_update_time:
        print("update")
        with open(configuration_path, 'r') as f:
            configuration = json.load(f)
        mumble_client.update_configuration(configuration)

        next_thread = threading.Timer(refresh_time, check_configuration_update,
                        args=(mumble_client, configuration_path, update_time, refresh_time))
        next_thread.daemon = True
        next_thread.start()

    else:
        print("no update")
        next_thread = threading.Timer(refresh_time, check_configuration_update,
                        args=(mumble_client, configuration_path, last_update_time, refresh_time))
        next_thread.daemon = True
        next_thread.start()


if __name__ == "__main__":
    server = sys.argv[1]
    nickname = sys.argv[2]
    configuration_path = sys.argv[3]

    with open(configuration_path, 'r') as f:
        configuration = json.load(f)
    mumbler = MumbleClient("***REMOVED***", nickname, configuration=configuration)
    # mumbler = MumbleClient("***REMOVED***", "***REMOVED***Only", configuration=configuration)

    check_configuration_update(mumbler, "example_config.json", os.path.getmtime("example_config.json"), 2)

    keyboard.wait("esc")
    print("Exited")
