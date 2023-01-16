import json
import sys
import os
import time
import keyboard
import pyaudio
import threading

import pymumble_py3
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED as PCS
from pymumble_py3.messages import MoveCmd, ModUserState

import send_event_reports

# pyaudio constants
CHUNKSIZE = 1024
FORMAT = pyaudio.paInt16  # pymumble soundchunk.pcm is 16 bits
PYAUDIO_CHANNELS = 1
RATE = 48000  # pymumble soundchunk.pcm is 48000Hz


class MumbleClient:
    def __init__(self, server, nickname, pwd="", configuration=None, exercise_id=20):
        if configuration is None:
            raise Exception(f"Invalid configuration: {configuration}")

        self.pwd = pwd
        self.server = server
        self.nickname = nickname

        self.configuration = configuration

        self.mumble: pymumble_py3.Mumble = None  # Defined in _create_mumble_instance
        self.p: pyaudio.PyAudio = None  # Defined in _setup_audio
        self.stream: pyaudio.Stream = None  # Defined in _setup_audio

        self.exercise_id = exercise_id
        self._already_speaking = False
        self._muted = False

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
        keyboard.on_press_key(self.configuration["speak"], self._start_talking)
        keyboard.on_release_key(self.configuration["speak"], self._stop_talking)

        keyboard.add_hotkey(
            self.configuration["StartListening"],
            self.change_channel_listening_status,
            args=([], True)
        )
        keyboard.add_hotkey(
            self.configuration["StopListening"],
            self.change_channel_listening_status,
            args=([], False)
        )
        person_type = None

        for user_type in self.configuration["UserTypes"]:
            if self.nickname in self.configuration["UserTypes"][user_type]:
                person_type = user_type
                break

        if person_type is not None:
            for hook in self.configuration["UserTypeConfigurations"][person_type]:
                keyboard.add_hotkey(hook, self.change_channel, args=(
                    self.configuration["UserTypeConfigurations"][person_type][hook],))

    def _start_talking(self, key_event: keyboard.KeyboardEvent):
        if not self._already_speaking and not self._muted:
            send_event_reports.voice_chat_change_recording(0, self.mumble.my_channel()["name"], self.nickname,
                                                           exercise_id=self.exercise_id)
            self._already_speaking = True

    def _stop_talking(self, key_event: keyboard.KeyboardEvent):
        if not self._muted:
            send_event_reports.voice_chat_change_recording(1, self.mumble.my_channel()["name"], self.nickname,
                                                           exercise_id=self.exercise_id)
            self._already_speaking = False

    def update_configuration(self, configuration: dict):
        self.configuration = configuration

        keyboard.unhook_all()

        self._setup_keyboard_hooks()

    def change_channel_listening_status(self, channels: list[str] = None, listen: bool = True):
        if channels is None or len(channels) == 0:
            channels = [self.mumble.my_channel()["name"]]

        channel_ids = []
        for channel_name in channels:
            channel_ids.append(self.mumble.channels.find_by_name(channel_name)["channel_id"])

        if listen:
            cmd = "listening_channel_add"
        else:
            cmd = "listening_channel_remove"

        self.mumble.commands.new_cmd(
            ModUserState(
                self.mumble.users.myself_session, {
                    "session": self.mumble.users.myself_session,
                    cmd: channel_ids
                }
            )
        )

    def change_channel(self, channel_data):
        # self.stop_all_listening()
        if channel_data["ChannelName"] == self.mumble.my_channel()["name"]:
            return

        send_event_reports.voice_chat_change_channel(self.mumble.my_channel()["name"],
                                                     channel_data["ChannelName"], self.nickname,
                                                     exercise_id=self.exercise_id)

        self.mumble.execute_command(
            MoveCmd(self.mumble.users.myself_session,
                    self.mumble.channels.find_by_name(channel_data["ChannelName"])["channel_id"]))

        time.sleep(0.1)
        if channel_data["CanTalk"]:
            self.mumble.users[self.mumble.users.myself_session].unmute()
            self._muted = False
            print("Unmuted")
        else:
            self.mumble.users[self.mumble.users.myself_session].mute()
            self._muted = True
            print("Muted")
        # if "ListeningChannels" in channel_data:
        #     self.start_listening_to_channels(channel_data["ListeningChannels"])

    def sound_retriever_handler(self, user, soundchunk):
        self.stream.write(soundchunk.pcm)

    def audio_capture(self):
        starting_time = time.time()
        while time.time() - starting_time < 0.05:
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
