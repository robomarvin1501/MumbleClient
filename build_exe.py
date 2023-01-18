import PyInstaller.__main__

# The following python doesn't seem to do the job properly, no idea why. Doesn't matter though, since the terminal
# commands do
PyInstaller.__main__.run([
    "main.py",
    r'--add-binary ".\opus.dll;."',
    "--noconsole",
    "--onefile"
])

# The following command creates the exe from the terminal.
# pyinstaller.exe .\main.py --add-binary ".\opus.dll;." --onefile --noconsole --name mumble_voice_chat