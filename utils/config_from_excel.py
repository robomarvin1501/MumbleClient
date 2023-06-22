"""
Builds the config from the Excel spreadsheet
It's an ugly, bodged together piece of code, that needs fixing every time it runs,
but it's better than doing it by hand
"""
import pandas as pd
import json

"""
0: listen no speak
1: speak on press
2: always speak
"""

sheet_name = "sheet_name"
excel_config: pd.DataFrame = pd.read_excel(r"../excel_configs/excel_config.xlsx", sheet_name=sheet_name)

user_types = dict()

config = {
    "speak": ["`", ";"],
    "StartListening": "+",
    "StopListening": "-",
    "exercise_id": 20,
    "UserTypeConfigurations": {},
    "UserTypes": {}
}


def get_hooks_from_numstring(numstring: str, channel_names: list[str]):
    hooks = {}
    hook_number = 0
    for i, v in enumerate(numstring):
        if v == "-":
            continue
        elif v == '0':
            hooks[str(hook_number)] = {
                "ChannelName": channel_names[i],
                "CanTalk": False,
                "AlwaysTalking": False
            }
            hook_number += 1
        elif v == "1":
            hooks[str(hook_number)] = {
                "ChannelName": channel_names[i],
                "CanTalk": True,
                "AlwaysTalking": False
            }
            hook_number += 1
        elif v == '2':
            hooks[str(hook_number)] = {
                "ChannelName": channel_names[i],
                "CanTalk": True,
                "AlwaysTalking": True
            }
            hook_number += 1
    return hooks


options = list("-012")
for index, row in excel_config.loc[:, "computer name":].iterrows():
    user_type = ""
    for i, v in enumerate(row["group":]):
        option = f"{v}"
        if option in options:
            user_type += option
        else:
            raise ValueError(option)

    if user_type not in user_types:
        user_types[user_type] = []

    user_types[user_type].append(row["computer name"])

for user_type in user_types:
    if user_type not in config["UserTypeConfigurations"]:
        config["UserTypeConfigurations"][user_type] = {}

    config["UserTypeConfigurations"][user_type] = get_hooks_from_numstring(user_type, list(row.index)[1:])

    config["UserTypes"][user_type] = user_types[user_type]

output_config_name = input(f"The current sheet name is: {sheet_name}.\nWhat should this config file be called: ")
if output_config_name == "":
    output_config_name = sheet_name
with open(f"../excel_configs/{output_config_name}.json", 'w', encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False)
