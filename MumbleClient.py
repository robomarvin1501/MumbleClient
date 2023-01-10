import json
import time

import keyboard
import pyaudio
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
    def __init__(self, server, nickname, pwd="", person_type="", configuration=None):
        if configuration is None:
            raise Exception(f"Invalid configuration: {configuration}")

        self.pwd = pwd
        self.server = server
        self.nickname = nickname

        self.configuration = configuration
        self.person_type = person_type

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

    def _get_channel_id_from_name(self, channel_name: str):
        for channel_id in self.mumble.channels.keys():
            if self.mumble.channels[channel_id]["name"] == channel_name:
                return channel_id
        return 0

    def _setup_keyboard_hooks(self):
        keyboard.add_hotkey(self.configuration["speak"], self.audio_capture)

        if self.person_type in self.configuration["configurations"]:
            for hook in self.configuration["configurations"][self.person_type]:
                keyboard.add_hotkey(hook[0], self.change_channel, args=(hook[1],))

    def change_channel(self, target_channel_name):
        self.mumble.execute_command(
            MoveCmd(self.mumble.users.myself_session, self._get_channel_id_from_name(target_channel_name)))

    def sound_retriever_handler(self, user, soundchunk):
        self.stream.write(soundchunk.pcm)

    def audio_capture(self):
        starting_time = time.time()
        while time.time() - starting_time < 1:
            data = self.stream.read(CHUNKSIZE, exception_on_overflow=False)
            self.mumble.sound_output.add_sound(data)


if __name__ == "__main__":
    with open("example_config.json", 'r') as f:
        configuration = json.load(f)
    mumbler = MumbleClient("***REMOVED***", "John", person_type="SuperUser", configuration=configuration)

    keyboard.wait("esc")
    print("Exited")
