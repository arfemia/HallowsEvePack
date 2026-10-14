# Seasons of Orbis

A standalone Hytale content pack of yearly events: Hallow's Eve from October 1 to November 12 and Hytale's Anniversary every January 13. Each season brings a host to the Forgotten Temple with quests, a daily board, a stall and achievements, and every season shares one reputation, Festival Favor, and one wallet, Festival Tokens. It never needs MMO Skill Tree.

## Requirements

- Hytale's Update 7
- Ziggfreed's CommonLib (ZiggfreedCommon) 2.4.0 or newer
- RPG Stations 1.1.1 or newer, which runs the Carving Bench
- MMO Skill Tree 1.7.1 or newer, optional

## Install

1. Install Ziggfreed's CommonLib and RPG Stations.
2. Drop the `SeasonsOfOrbis-<version>.zip` into your server's `Mods/` folder beside them.
3. Start the server. While a season runs, its host is in the Forgotten Temple.

## Hallow's Eve

From October 1 to November 12, Old Jack, a pumpkin-headed host, sets up in the Forgotten Temple. He brings a questline that ends in lighting the Hollow Lantern, three dailies and a board with work for the dark and the daylight every day, and a stall that takes Hallow Sweets: Lantern Bombs in four tiers, a Costume Wand, the game's own Halloween Broomstick, the Hallowed gear set, and five of Update 7's gadgets (the Spyglass, Goblin Repair Kits, the Scrap Glider, the Hookshot and Hook Anchors) that open with favor. Ask every character with a conversation for a treat, once a day each: with MMO Skill Tree or another pack that gives characters conversations, every one of them plays along, and on this pack alone only Old Jack does. Earn the season's achievements: a yearly keepsake among them, and the title "the Hallowed" for earning them all. The Almanac keeps your tallies. Unspent sweets carry over to next year.

Two reputations grow over the seasons: Old Jack's Favor, from Stranger to Jack's Own, and the Hallowed, a reputation that keeps counting past Exalted with a cache every so often. Old Jack's quests and board jobs pay favor with both, and the night's creatures and trick-or-treat raise your favor with the Hallowed. While you wear the Jack Helm, you earn more favor with Old Jack, and the Jack Shield does the same for the Hallowed. His favor opens a second night job and a second day job on his board, and at Confidant it earns Jack's Confidant and its title. The top ranks open two charred pieces of the Hallowed set at his stall: the Burning Jack Helm (Revered with the Hallowed, or Jack's Own with Old Jack) and the Flaming Jack Shield (Exalted with the Hallowed). He pays a little favor when you stop by once a day, and "How do we stand?" opens the Reputation page.

After dark Jack Skeletons, Hollow Ghouls and Lost Souls come out, and Geode Wraiths haunt the mineshafts. Mining turns up Cursed Geodes, and pumpkins sometimes come up hallowed. From October 28 to November 1, Harvest Moon brings out about twice the creatures.

The Carving Bench, crafted at a Workbench, carves lanterns, the Jack Helm and Lantern Bombs all year. Its Hallowed recipe, the Jack Shield, opens only during the event.

## Every season

- Festival Favor, a reputation every season shares, runs up to Exalted and on through Exalted II, III and IV. Old Jack's quests (all but the first) and his Night and Day jobs pay it.
- Festival Tokens, the wallet every season shares, carry over from season to season and spend at the Festival Shelf in each host's stall, on decorations from the game's own festivals. Exalted II and Exalted III open the Goblin Plushie and the Carved Kweebec Figure there.
- Three achievements count keepsakes from different seasons: Season to Season, Round the Year and Seasons of Orbis, which gives the title "Friend of the Seasons".
- Hytale's Anniversary: every January 13 from 2027, being on the server earns that year's anniversary achievement and the title "the Ever-Present".

Server owners switch any event off, or move its days, in `mods/ziggfreedcommon/calendar.json`, and `/zigcalendar status <event>` shows what the server reads.

## With other mods

- **With MMO Skill Tree** (1.7.1+), Hallow's Eve trains skills: Lantern Bombs train Artillery, Old Jack's rewards and the cracked geodes pay skill XP, his board posts a Skill job every day that pays favor like his own, the Hallowed set adds luck and Artillery damage, the Carving Bench trains Crafting, and Harvest Moon lifts Harvesting and Artillery XP. The pack never needs MMO Skill Tree.
- **With the MMO Skill Bounty Pack** (1.3.0+), the Daily bounty board posts a haunt contract each day of Hallow's Eve.

1.2.0 adds the Headless Horseman, Hallow's Eve's boss, fought in his own graveyard through the Gravekeeper beside Old Jack, and puts Old Jack's board jobs and errands on his own quest page. Beside MMO Skill Tree 1.7.2, the Horseman pays Defense XP. Harvest Feast, the next season, comes later this year. 1.1.0 added Festival Favor and Festival Tokens, the Seasons of Orbis achievements and Hytale's Anniversary. 1.0.0 was the pack's first release, beside MMO Skill Tree 1.7.0.

## Build

```powershell
.\build.ps1                  # build the zip, and install it if a Mods folder is known
.\build.ps1 -Install:$false  # build only, no copy
.\build.ps1 -ModsDir <path>  # build, then install into that folder
```

Produces `SeasonsOfOrbis-<version>.zip` (forward-slash entries plus explicit directory entries, which the bundled `.lang` files need). The script is cross-platform (`pwsh ./build.ps1` works on macOS/Linux). To have it also copy the zip into your Hytale `Mods/` folder, set `HYTALE_MODS_DIR` once to that folder (or pass `-ModsDir <path>`).
