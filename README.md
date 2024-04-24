# Mod Importer

Defines and executes a [format](https://github.com/SGG-Modding/sgg-mod-format/wiki/Format-Specification) for modifying the data files of SuperGiant Games' games.

For Hades II, it imports lua scripts, merges sjson edits, and performs file replacement.

If you have any questions you can join the [url=https://discordapp.com/invite/KuMbyrN]Hades Modding Discord[/url].

## Install

### Windows
- Download [modimporter-windows.zip](https://github.com/SGG-Modding/sgg-mod-modimporter/releases/latest/download/modimporter-windows.zip).
- Extract the archive: you should get a `modimporter.exe` executable.
- Move `modimporter.exe` into the `Content` directory of your game files:
    - Steam: *Library* > Right-click on ﻿Hades II > *Manage* > *Browse local files* > `Content`
    - ﻿Epic Games: *N/A* (not released yet)
    - Microsoft Store: *N/A* (not released yet)
- Create a new directory named `Mods` (if there is not already one), then put any mods you like in it (for example: `ModUtil`).
    - Each mod must have its own directory and a `modfile.txt`. *If a mod does not have that, it is not compatible.* The folder structure should look something like:
```
Content/
├── Audio/
├── ...
├── modimporter.exe
└── Mods/
    ├── ModUtil/
    │   ├── ...
    │   └── modfile.txt
    └── AnotherMod/
       ├── ...
        └── modfile.txt
```
- Run `modimporter.exe` by double-clicking on it.
- *Important:* `modimporter.exe` must be run again everytime you add / remove mods in `Content/Mods`, and also every time the game is updated.

### macOS
- Hades II has not been released in any form for macOS yet.

## More documentation
[Github Wiki: The Mod Importer](https://github.com/SGG-Modding/sgg-mod-format/wiki/The-Mod-Importer)
[Github Wiki: Installing Mods](https://github.com/SGG-Modding/sgg-mod-format/wiki/Installing-Mods-%7C-The-Mods-Folder)