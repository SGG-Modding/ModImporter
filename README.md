# Mod Importer

For SuperGiantGames's games (To be replaced by SGGMI)

https://www.nexusmods.com/hades/mods/26

## Development

### Release workflow

New releases can be created from GitHub Actions using the release workflow
available [here](https://github.com/SGG-Modding/sgg-mod-modimporter/actions/workflows/release.yaml).

The release workflow takes a tag / release name as input parameter to tag the
repository, create a new release, build binaries, and upload them to the
release.

If the tag / release name is omitted and left blank, the workflow will run in
dry-run mode (no tag / release, only binaries build) for testing purposes.

### Build binaries locally

- Install [PyInstaller](https://pypi.org/project/pyinstaller/):

```bat
python -m pip install pyinstaller==4.0
```

> Note that we use version 4.0 instead of the latest version to avoid getting
> flagged by too many antivirus solutions due to PyInstaller's
> pre-compiled bootloader. Older versions are less susceptible to this as AV
> solutions had more time to properly recognize and whitelist them, in particular
> from Microsoft antivirus (which is the single most important one not to get
> flagged by).

- Build binaries:

```bat
python -m PyInstaller --onefile modimporter.py --name modimporter
```
