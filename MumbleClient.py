import datetime
import json
import os
import sys
import time
import keyboard
import pyaudio
import audioop
import threading

import tkinter as tk

import pymumble_py3
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED as PCS
from pymumble_py3.messages import MoveCmd, ModUserState

import send_event_reports

COLOURS = {
    "red": "#FF0000",
    "dark-red": "#AA0000",
    "green": "#00FF00",
    "dark-green": "#00AA00",
    "yellow": "#DDAA00"
}


class Mumbler:
    def __init__(self, server, nickname, configuration_path):
        with open(configuration_path, 'r', encoding="utf-8") as f:
            configuration = json.load(f)

        self.non_selected_thickness = 5
        self.selected_thickness = 15

        self.muted_background = COLOURS["red"]
        self.listening_background = COLOURS["yellow"]
        self.talking_background = COLOURS["dark-green"]

        self.not_talking_highlight = COLOURS["dark-red"]
        self.talking_highlight = COLOURS["green"]

        self.window = tk.Tk()
        self.window.title(f"***REMOVED***-{nickname}")
        self.frames: dict[str, tk.Frame] = dict()
        self.labels: dict[str, tk.Label] = dict()

        self.current_channel: str = ""
        self.muted: bool = False
        self.listening_channels: set[str] = set()

        self.stop_showing_talking_timer: threading.Timer = None

        for user_type in configuration["UserTypes"]:
            if nickname in configuration["UserTypes"][user_type]:
                self.person_type = user_type
                break
        else:
            sys.exit()

        self._setup_ui(configuration)

        self.mumble_client = MumbleClient(server, nickname, gui=self, configuration=configuration)

    def _get_channel_names_and_keys(self, configuration: dict):
        person_type_config = configuration["UserTypeConfigurations"][self.person_type]
        channel_names_and_keys = []
        for key in person_type_config:
            channel_names_and_keys.append([key, person_type_config[key]["ChannelName"]])

        return channel_names_and_keys

    def _setup_ui(self, configuration: dict):
        frame_width = 100
        frame_height = 70
        for channel_num, channel_name in (channel_names_and_keys := self._get_channel_names_and_keys(configuration)):
            frame = tk.Frame(master=self.window, width=frame_width, height=frame_height,
                             bg=self.muted_background)
            frame.config(highlightbackground=self.not_talking_highlight, highlightthickness=self.non_selected_thickness)

            frame.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

            self.frames[channel_name] = frame

            label = tk.Label(master=frame, text=f"{channel_name}\n{channel_num}", bg=self.muted_background)
            label.place(anchor="center", relx=0.5, rely=0.5)
            self.labels[channel_name] = label

        width = frame_width * len(channel_names_and_keys)
        height = frame_height
        xpos = self.window.winfo_screenwidth() - (width + 50)
        ypos = self.window.winfo_screenheight() - (height + 50)

        self.window.geometry(f"{width}x{height}+{xpos}+{ypos}")

        self.window.attributes("-topmost", True)
        self.window.update()

    def change_channel(self, channel_data: dict[str]):
        if self.current_channel != "":
            self.frames[self.current_channel].config(highlightthickness=self.non_selected_thickness)

        self.current_channel = channel_data["ChannelName"]
        self.muted = not channel_data["CanTalk"]

        self.frames[self.current_channel].config(highlightthickness=self.selected_thickness)

        self.set_all_frame_colours()

    def talk(self, talking: bool = False):
        if self.current_channel == "":
            return
        if talking:
            self.frames[self.current_channel].config(highlightbackground=self.talking_highlight)
        else:
            self.frames[self.current_channel].config(highlightbackground=self.not_talking_highlight)

    def set_all_frame_colours(self):
        for channel_name in self.frames.keys():
            if channel_name == self.current_channel:
                if self.muted:
                    self.set_frame_colour(channel_name, "listening")
                else:
                    self.set_frame_colour(channel_name, "talking")
            else:
                if channel_name in self.listening_channels:
                    self.set_frame_colour(channel_name, "listening")
                else:
                    self.set_frame_colour(channel_name, "muted")

    def set_frame_colour(self, channel_name: str, type: str):
        if type == "muted":
            self.frames[channel_name].config(bg=self.muted_background)
            self.labels[channel_name].config(bg=self.muted_background)
        elif type == "listening":
            self.frames[channel_name].config(bg=self.listening_background)
            self.labels[channel_name].config(bg=self.listening_background)
        elif type == "talking":
            self.frames[channel_name].config(bg=self.talking_background)
            self.labels[channel_name].config(bg=self.talking_background)

    def show_someone_else_talking(self, channel_name: str, talking: bool = False):
        if talking:
            try:
                self.labels[channel_name].config(bg=self.talking_highlight)
            except RuntimeError:
                pass
            self.stop_showing_talking_timer = threading.Timer(0.1, self.show_someone_else_talking,
                                                              args=(channel_name, False))
            self.stop_showing_talking_timer.start()
        else:
            self.set_all_frame_colours()


# pyaudio constants
CHUNKSIZE = 1024
FORMAT = pyaudio.paInt16  # pymumble soundchunk.pcm is 16 bits
PYAUDIO_CHANNELS = 1
RATE = 48000  # pymumble soundchunk.pcm is 48000Hz


class MumbleClient:
    def __init__(self, server, nickname, pwd="", gui: Mumbler = None, configuration=None, command_timeout: float = 0.8,
                 exercise_id=20):
        if configuration is None:
            raise Exception(f"Invalid configuration: {configuration}")

        self.pwd = pwd
        self.server = server
        self.nickname = nickname

        self.configuration = configuration
        self.gui = gui

        self.mumble: pymumble_py3.Mumble = None  # Defined in _create_mumble_instance
        self.p: pyaudio.PyAudio = None  # Defined in _setup_audio
        self.streams: dict[str, pyaudio.Stream] = None
        self.person_type: str = None  # Defined in _setup_keyboard_hooks

        self.exercise_id = exercise_id
        self._already_speaking = False
        self._muted = False

        self.internal_chat = False
        self.always_talking_thread: threading.Thread = threading.Thread(target=self.always_talking_audio_capture,
                                                                        daemon=True)
        self.internal_channel: list[str] = None
        self.current_target: list[str] = None
        self.listen: set[str] = set()
        self.last_command_timestamp = 0
        self.command_timeout = command_timeout

        self._setup_audio()
        self._create_mumble_instance()
        self._setup_keyboard_hooks()
        self._set_internal_chat()

        self._move_to_starting_channel()

    def __exit__(self, exc_type, exc_val, exc_tb):
        for stream in self.streams.values():
            stream.stop_stream()
            stream.close()
        self.p.terminate()

    def _create_mumble_instance(self):
        self.mumble = pymumble_py3.Mumble(self.server, self.nickname, password=self.pwd)
        self.mumble.callbacks.set_callback(PCS, self.sound_retriever_handler)
        self.mumble.set_receive_sound(1)
        self.mumble.start()
        self.mumble.is_ready()

    def _setup_audio(self):
        self.p = pyaudio.PyAudio()
        self.streams = dict()
        self._open_new_audio_stream("i_am_talking")

    def _open_new_audio_stream(self, person):
        self.streams[person] = self.p.open(format=FORMAT,
                                           channels=PYAUDIO_CHANNELS,
                                           rate=RATE,
                                           input=True,
                                           output=True,
                                           frames_per_buffer=CHUNKSIZE)

    def _setup_keyboard_hooks(self):
        for speak_key in self.configuration["speak"]:
            try:
                keyboard.add_hotkey(speak_key, self.audio_capture)
                keyboard.on_press_key(speak_key, self._start_talking)
                keyboard.on_release_key(speak_key, self._stop_talking)
            except ValueError:
                pass

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

        keyboard.add_hotkey(
            self.configuration["StartListening"],
            self.always_listening,
            args=([], True)
        )

        keyboard.add_hotkey(
            self.configuration["StopListening"],
            self.always_listening,
            args=([], False)
        )

        person_type = None

        for user_type in self.configuration["UserTypes"]:
            if self.nickname in self.configuration["UserTypes"][user_type]:
                person_type = user_type
                break

        if person_type is not None:
            self.person_type = person_type
            for hook in self.configuration["UserTypeConfigurations"][person_type]:
                keyboard.add_hotkey(hook, self.change_channel, args=(
                    self.configuration["UserTypeConfigurations"][person_type][hook],))

    def _set_internal_chat(self):
        for channel_num in self.configuration["UserTypeConfigurations"][self.person_type]:
            channel_config = self.configuration["UserTypeConfigurations"][self.person_type][channel_num]
            if "AlwaysTalking" in channel_config and channel_config["AlwaysTalking"]:
                self.internal_chat = True
                self.internal_channel = [channel_config["ChannelName"]]
                self.always_talking_thread.start()
                return

    def _move_to_starting_channel(self):
        if not self.internal_chat:
            self.change_channel((channel_data := self.configuration["UserTypeConfigurations"][self.person_type][
                list(self.configuration["UserTypeConfigurations"][self.person_type].keys())[0]]))
            self.gui.change_channel(channel_data)
        else:
            for channel_num in self.configuration["UserTypeConfigurations"][self.person_type]:
                channel_config = self.configuration["UserTypeConfigurations"][self.person_type][channel_num]
                if "AlwaysTalking" in channel_config and channel_config["AlwaysTalking"]:
                    self.change_channel(channel_config)

    def _start_talking(self, key_event: keyboard.KeyboardEvent):
        if not self._already_speaking and not self._muted:
            if self.internal_chat and self.current_target is not None:
                self.mumble.execute_command(MoveCmd(self.mumble.users.myself_session,
                                                    self.mumble.channels.find_by_name(self.current_target[0])[
                                                        "channel_id"]))
            send_event_reports.voice_chat_change_recording(0, self.mumble.my_channel()["name"], self.nickname,
                                                           exercise_id=self.exercise_id)
            self._already_speaking = True
            self.gui.talk(True)

    def _stop_talking(self, key_event: keyboard.KeyboardEvent):
        if not self._muted:
            if self.internal_chat:
                target_channel = self.mumble.channels.find_by_name(self.internal_channel[0])
                self.mumble.execute_command(MoveCmd(self.mumble.users.myself_session, target_channel["channel_id"]))
            send_event_reports.voice_chat_change_recording(1, self.mumble.my_channel()["name"], self.nickname,
                                                           exercise_id=self.exercise_id)
            self._already_speaking = False
            self.gui.talk(False)

    def update_configuration(self, configuration: dict):
        self.configuration = configuration

        keyboard.unhook_all()

        self._setup_keyboard_hooks()

    def always_listening(self, channels: list[str] = None, listen: bool = True):
        if (channels == None or channels == []) and self.current_target is not None:
            channels = self.current_target
        channels = set(channels)
        if listen:
            self.listen |= channels
        else:
            self.listen.difference_update(channels)

    def change_channel_listening_status(self, channels: list[str] = None, listen: bool = True):
        if channels is None or len(channels) == 0:
            channels = [self.mumble.my_channel()["name"]]

        channel_ids = []
        for channel_name in channels:
            channel_ids.append(self.mumble.channels.find_by_name(channel_name)["channel_id"])

        if listen:
            cmd = "listening_channel_add"
            self.gui.listening_channels |= set(channels)
            self.gui.set_all_frame_colours()
        else:
            for channel in channels:
                if channel in self.listen:
                    channels.remove(channel)
            cmd = "listening_channel_remove"
            self.gui.listening_channels.difference_update(channels)
            self.gui.set_all_frame_colours()

        self.mumble.execute_command(
            ModUserState(
                self.mumble.users.myself_session, {
                    "session": self.mumble.users.myself_session,
                    cmd: channel_ids
                }
            )
        )

    def change_channel(self, channel_data):
        # self.stop_all_listening()
        current_time = datetime.datetime.now().timestamp()
        if current_time - self.last_command_timestamp < self.command_timeout:
            return
        self.last_command_timestamp = current_time
        if channel_data["ChannelName"] == self.mumble.my_channel()["name"] or (
                self.internal_chat and self.current_target == [channel_data["ChannelName"]]):
            if self.internal_chat and self.current_target is not None:
                stop_listening_targets = list(set(self.current_target) - self.listen)
                self.current_target = [channel_data["ChannelName"]]
                self.change_channel_listening_status(stop_listening_targets, False)
                self.gui.change_channel(channel_data)
            return

        if self.internal_chat and self.mumble.my_channel()["name"] != "Root":
            if self.current_target is not None:
                stop_listening_targets = list(set(self.current_target) - self.listen)
            else:
                stop_listening_targets = self.current_target
            self.change_channel_listening_status(stop_listening_targets, False)
            if channel_data["CanTalk"]:
                self.current_target = [self.mumble.channels.find_by_name(channel_data["ChannelName"])["name"]]
            self.change_channel_listening_status(self.current_target, True)
        else:
            self.mumble.execute_command(
                MoveCmd(self.mumble.users.myself_session,
                        self.mumble.channels.find_by_name(channel_data["ChannelName"])["channel_id"]))

        time.sleep(0.1)
        if self.mumble.my_channel()["name"] == channel_data["ChannelName"] or self.internal_chat:
            send_event_reports.voice_chat_change_channel(self.mumble.my_channel()["name"],
                                                         channel_data["ChannelName"], self.nickname,
                                                         exercise_id=self.exercise_id)
            if channel_data["CanTalk"]:
                self.mumble.users[self.mumble.users.myself_session].unmute()
                self._muted = False
            else:
                self.mumble.users[self.mumble.users.myself_session].mute()
                self._muted = True

            self.gui.change_channel(channel_data)

        if self.internal_chat:
            self.gui.change_channel(channel_data)
        # if "ListeningChannels" in channel_data:
        #     self.start_listening_to_channels(channel_data["ListeningChannels"])

    def sound_retriever_handler(self, user, soundchunk):
        if type(self.gui.stop_showing_talking_timer) == threading.Timer:
            self.gui.stop_showing_talking_timer.cancel()
        talking_channel = self.mumble.channels[user["channel_id"]]["name"]
        self.gui.show_someone_else_talking(talking_channel, True)
        try:
            self.streams[user["session"]].write(soundchunk.pcm)
        except KeyError:
            self._open_new_audio_stream(user["session"])
            self.streams[user["session"]].write(soundchunk.pcm)

    def always_talking_audio_capture(self):
        while True:
            self.audio_capture()

    def audio_capture(self):
        starting_time = time.time()
        while time.time() - starting_time < 0.05:
            data = self.streams["i_am_talking"].read(CHUNKSIZE, exception_on_overflow=False)
            rms = audioop.rms(data, 2)
            if rms > 200:
                self.mumble.sound_output.add_sound(data)


def check_configuration_update(mumble_client: MumbleClient, configuration_path: str, last_update_time: float,
                               refresh_time: int = 10):
    update_time = os.path.getmtime(configuration_path)
    if update_time > last_update_time:
        with open(configuration_path, 'r') as f:
            configuration = json.load(f)
        mumble_client.update_configuration(configuration)

        next_thread = threading.Timer(refresh_time, check_configuration_update,
                                      args=(mumble_client, configuration_path, update_time, refresh_time))
        next_thread.daemon = True
        next_thread.start()

    else:
        next_thread = threading.Timer(refresh_time, check_configuration_update,
                                      args=(mumble_client, configuration_path, last_update_time, refresh_time))
        next_thread.daemon = True
        next_thread.start()


if __name__ == "__main__":
    config = "example_config.json"
    mblr = Mumbler("***REMOVED***", "Alex", config)
    check_configuration_update(mblr.mumble_client, config, os.path.getmtime("example_config.json"), 2)

    mblr.window.mainloop()

    # server = sys.argv[1]
    # nickname = sys.argv[2]
    # configuration_path = sys.argv[3]
    #
    # with open(configuration_path, 'r', encoding="utf-8") as f:
    #     configuration = json.load(f)
    # mumbler = MumbleClient("***REMOVED***", nickname, configuration=configuration)
    # # mumbler = MumbleClient("***REMOVED***", "***REMOVED***Only", configuration=configuration)
    #
    # check_configuration_update(mumbler, "example_config.json", os.path.getmtime("example_config.json"), 2)
    #
    # keyboard.wait("esc")
    # print("Exited")
