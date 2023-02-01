"""
Removes all old channels from the server, and adds the ones detailed in the excel spreadsheet
"""

import pandas as pd
import pymumble_py3
import time

***REMOVED*** = "***REMOVED*** ***REMOVED*** 1"
excel_config: pd.DataFrame = pd.read_excel(r"***REMOVED***_excel/***REMOVED***_***REMOVED***.xlsx", sheet_name=***REMOVED***)

channel_names = list(excel_config.loc[:, "***REMOVED*** ***REMOVED*** 1":].columns)
print(channel_names)

mumble: pymumble_py3.Mumble = pymumble_py3.Mumble("***REMOVED***", "SuperUser", password="not***REMOVED***")
mumble.start()
mumble.is_ready()

for channel in list(mumble.channels.keys()):
    mumble.channels.remove_channel(channel)
    time.sleep(0.2)

for channel in channel_names:
    mumble.channels.new_channel(0, channel)
    time.sleep(0.2)
