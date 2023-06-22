"""
Removes all old channels from the server, and adds the ones detailed in the excel spreadsheet
"""

import pandas as pd
import pymumble_py3
import time

sheet_name = "sheet_name"
excel_config: pd.DataFrame = pd.read_excel(r"excel_configs/excel_config.xlsx", sheet_name=sheet_name)

channel_names = list(excel_config.loc[:, "team_channel":].columns)
print(channel_names)

mumble: pymumble_py3.Mumble = pymumble_py3.Mumble("mumble_server", "SuperUser", password="password")
mumble.start()
mumble.is_ready()

for channel in list(mumble.channels.keys()):
    mumble.channels.remove_channel(channel)
    time.sleep(0.2)

for channel in channel_names:
    mumble.channels.new_channel(0, channel)
    time.sleep(0.2)
