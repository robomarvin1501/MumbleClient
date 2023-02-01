"""
Builds the config from the excel spreadsheet
It's an ugly, bodged together piece of code, that needs fixing every time it runs,
but it's better than doing it by hand
"""
import pandas as pd
import json

***REMOVED*** = "***REMOVED*** ***REMOVED*** 1"
excel_config: pd.DataFrame = pd.read_excel(r"***REMOVED***_excel/***REMOVED***_***REMOVED***.xlsx", sheet_name=***REMOVED***)


user_types = dict()

config = {
    "speak": "`",
    "StartListening": "+",
    "StopListening": "-",
    "UserTypeConfigurations": {},
    "UserTypes": {}
}


def get_hooks_from_numstring(numstring: str, channel_names: list[str], internal_index: str):
    hooks = {}
    hook_number = 0
    num_internal_index = channel_names.index(internal_index)
    for i, v in enumerate(numstring):
        if v == "0":
            continue
        elif v == "1":
            hooks[str(hook_number)] = {
                "ChannelName": channel_names[i],
                "CanTalk": True  # Will eventually be changed when the table is redone to consider those who cannot talk
            }
            if i + 1 > num_internal_index:
                hooks[str(hook_number)]["AlwaysTalking"] = True
            hook_number += 1
    return hooks


for index, row in excel_config.loc[:, "***REMOVED*** ***REMOVED***":].iterrows():
    user_type = ""
    for i, v in enumerate(row["***REMOVED*** ***REMOVED*** 1":]):
        if v == '-':
            user_type += '0'
        else:
            user_type += '1'

    if user_type not in user_types:
        user_types[user_type] = []

    user_types[user_type].append(row["***REMOVED*** ***REMOVED***"])

for user_type in user_types:
    if user_type not in config["UserTypeConfigurations"]:
        config["UserTypeConfigurations"][user_type] = {}

    config["UserTypeConfigurations"][user_type] = get_hooks_from_numstring(user_type, list(row.index)[1:],
                                                                           internal_index="***REMOVED*** ***REMOVED*** 3")

    config["UserTypes"][user_type] = user_types[user_type]

output_config_name = input(f"The current sheet name is: {***REMOVED***}.\nWhat should this config file be called: ")
if output_config_name == "":
    output_config_name = ***REMOVED***
with open(f"***REMOVED***_excel/{output_config_name}.json", 'w', encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False)
