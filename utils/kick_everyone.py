"""
This scripts kicks everyone, cos sometimes dammit, I need that username
"""
import pymumble_py3


mumble: pymumble_py3.Mumble = pymumble_py3.Mumble("mumble_server", "SuperUser", password="password")
mumble.start()
mumble.is_ready()

for user in list(mumble.users.values()):
    if user["name"] == "SuperUser":
        continue
    user.kick()

print("hello")