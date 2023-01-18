import PyInstaller.__main__

PyInstaller.__main__.run([
    "main.py",
    r'--add-binary ".\opus.dll;."',
    "--noconsole",
    "--onefile"
])

# pyinstaller.exe .\main.py --add-binary ".\opus.dll;." --onefile
