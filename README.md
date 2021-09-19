# Mod Importer
For SuperGiantGames's games (To be replaced by SGGMI)

https://www.nexusmods.com/hades/mods/26

## Development

Binaries can be built from GitHub Actions runners using the build workflow
available [here](https://github.com/SGG-Modding/sgg-mod-modimporter/actions/workflows/build.yaml).

To build binaries locally:

- Install [PyInstaller](https://pypi.org/project/pyinstaller/):

```bat
python -m pip install pyinstaller==4.0
```

> Note that we use version 4.0 instead of the latest version to avoid getting
flagged by too many antivirus solutions due to PyInstaller's
pre-compiled bootloader. Older versions are less susceptible to this as AV
solutions had more time to properly recognize and whitelist them, in particular
from Microsoft antivirus (which is the single most important one not to get
flagged by).

- Build binaries:

```bat
python -m PyInstaller --onefile modimporter.py --name modimporter
```
