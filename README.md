# Seasons of Orbis

A standalone Hytale content pack of yearly events. Its first is Hallow's Eve, an autumn event. It needs Ziggfreed's CommonLib (ZiggfreedCommon 2.2.0+) and RPG Stations (1.1.0+), which runs its Carving Bench. It never needs MMO Skill Tree.

From October 1 to November 3, Old Jack, a pumpkin-headed host, keeps the Forgotten Temple. He brings a questline that ends in lighting the Hollow Lantern, three dailies and a nightly board, a stall that takes Hallow Sweets, Lantern Bombs in four tiers, a Costume Wand and the Hallowed gear set. Ask any character with a conversation for a treat once a day: with MMO Skill Tree or another pack that gives characters conversations, every one of them plays along, and on this pack alone only Old Jack does. Earn the season's achievements: a yearly keepsake among them, and the title The Hallowed for earning them all. The Almanac keeps your tallies. Unspent sweets carry over to next year.

After dark Jack Skeletons, Hollow Ghouls and Lost Souls walk, and Geode Wraiths haunt the mineshafts. Mining turns up Cursed Geodes, and pumpkins sometimes come up hallowed. On the last three nights of October, Harvest Moon brings out about twice the creatures.

The Carving Bench, crafted at a Workbench, carves lanterns, the Jack Helm and Lantern Bombs all year. Its Hallowed recipe, the Jack Shield, opens only during the event.

- **With MMO Skill Tree** (1.7.0+), the season also trains skills. Lantern Bombs train Artillery, Old Jack's rewards and the cracked geodes pay skill XP, his board posts skill dailies on some nights, the Hallowed set adds luck and Artillery damage, the Carving Bench trains Crafting, and Harvest Moon lifts Harvesting and Artillery XP. None of it needs this pack to change, and the pack never needs MMO Skill Tree.
- **With the MMO Skill Bounty Pack** (1.3.0+), the Daily bounty board posts a haunt contract each day of the event.

1.0.0 is the pack's first release, beside MMO Skill Tree 1.7.0.

## Build

```powershell
.\build.ps1                  # build the zip, and install it if a Mods folder is known
.\build.ps1 -Install:$false  # build only, no copy
```

Produces `SeasonsOfOrbis-<version>.zip` (forward-slash entries plus explicit directory entries, which the bundled `.lang` files need). The script is cross-platform (`pwsh ./build.ps1` works on macOS/Linux). To have it also copy the zip into your Hytale `Mods/` folder, set `HYTALE_MODS_DIR` once to that folder (or pass `-ModsDir <path>`).
