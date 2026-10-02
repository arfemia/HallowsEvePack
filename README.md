# Hallow's Eve Pack

A standalone Hytale content pack for Hallow's Eve, a yearly autumn event. It needs only Ziggfreed's CommonLib (ZiggfreedCommon 2.2.0+), so it runs on any server with that library, MMO Skill Tree or not.

From October 1 to November 3, Old Jack, a pumpkin-headed host, keeps the Forgotten Temple. He brings a questline, daily tasks and a board, a vendor that takes Hallow Sweets, Lantern Bombs in four tiers, the Hallowed gear set, the Hallow King and the Hollow Crypt. Unspent sweets carry over to next year.

- **With MMO Skill Tree** (1.7.0+), the event pays skill XP, and the Hallowed set adds luck and Artillery damage.
- **With RPG Stations** (1.1.0+), the Carving Bench lets you carve lanterns, helms and bombs all year. Its Hallowed recipes open only during the event.

The pack is in development for its first release, 1.0.0, alongside MMO Skill Tree 1.7.0.

## Build

```powershell
.\build.ps1                  # build the zip, and install it if a Mods folder is known
.\build.ps1 -Install:$false  # build only, no copy
```

Produces `HallowsEvePack-<version>.zip` (forward-slash entries plus explicit directory entries, which the bundled `.lang` files need). The script is cross-platform (`pwsh ./build.ps1` works on macOS/Linux). To have it also copy the zip into your Hytale `Mods/` folder, set `HYTALE_MODS_DIR` once to that folder (or pass `-ModsDir <path>`).
