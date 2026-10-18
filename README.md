# Seasons of Orbis

A standalone Hytale content pack of yearly events: Hallow's Eve from October 1 to November 12 and Hytale's Anniversary every January 13. Each season brings a host to the Forgotten Temple with quests, a daily board, a shop and achievements, and every season shares one reputation, Festival Favor, and one wallet, Festival Tokens. It never needs MMO Skill Tree.

## Requirements

- Hytale's Update 7
- Ziggfreed's CommonLib (ZiggfreedCommon) 2.4.0 or newer
- RPG Stations 1.1.1 or newer, which runs the Carving Bench
- MMO Skill Tree 1.7.2 or newer, optional

## Install

1. Install Ziggfreed's CommonLib and RPG Stations.
2. Drop the `SeasonsOfOrbis-<version>.zip` into your server's `Mods/` folder beside them.
3. Start the server. While a season runs, its host is in the Forgotten Temple. A host takes its shop, boards and quests along when its placement's `Where` names another world in `mods/ziggfreedcommon/npc-placements.json`.

## Hallow's Eve

From October 1 to November 12, Old Jack, a pumpkin-headed host, sets up in the Forgotten Temple. He brings a questline that ends in lighting the Hollow Lantern, three dailies and a board with work for the dark and the daylight every day, and a shop that takes Hallow Sweets: Lantern Bombs in four tiers, Grave Candles, a Costume Wand, the game's own Halloween Broomstick, the Hallowed gear set, and five of Update 7's gadgets (the Spyglass, Goblin Repair Kits, the Scrap Glider, the Hookshot and Hook Anchors) that open with favor. Ask him "What needs doing?" and one list shows his quests, the day's board jobs and his errands. Ask every character with a conversation for a treat, once a day each: with MMO Skill Tree or another pack that gives characters conversations, every one of them plays along, and on this pack alone Old Jack and the Gravekeeper do. Earn the season's achievements: a yearly keepsake among them, and the title "the Hallowed" for earning them all. The Almanac keeps your tallies. Unspent sweets carry over to next year.

Two reputations grow over the seasons: Old Jack's Favor, from Stranger to Jack's Own, and the Hallowed, a reputation that keeps counting past Exalted with a cache every so often. Old Jack's quests and board jobs pay favor with both, and the night's creatures and trick-or-treat raise your favor with the Hallowed. While you wear the Jack Helm, you earn more favor with Old Jack, and the Jack Shield does the same for the Hallowed. His favor opens a second night job and a second day job on his board, and at Confidant it earns Jack's Confidant and its title. The top ranks open two charred pieces of the Hallowed set at his shop: the Burning Jack Helm (Revered with the Hallowed, or Jack's Own with Old Jack) and the Flaming Jack Shield (Exalted with the Hallowed). He pays a little favor when you stop by once a day, and "How do we stand?" opens the Reputation page.

After dark Jack Skeletons, Hollow Ghouls and Lost Souls come out, and Geode Wraiths haunt the mineshafts. Mining turns up Cursed Geodes, and pumpkins sometimes come up hallowed. From October 28 to November 1, Harvest Moon brings out about twice the creatures.

The Carving Bench, crafted at a Workbench, carves lanterns, the Jack Helm and Lantern Bombs all year. Its Hallowed recipe, the Jack Shield, opens only during the event.

### The Headless Horseman

The Headless Horseman rides his own graveyard. Buy a Grave Candle at Old Jack's shop and the Gravekeeper beside him burns it to let you in, alone or with up to four friends who follow you in free. The more of you there are, the tougher he gets. Four Jack Skeletons guard his fountain, and he rides out once they're down. He fights from the saddle, then on foot, and then his head flies off: he can't be hurt until you cut it down. Somewhere in the graveyard a hidden chest holds Lantern Bombs, full again every run.

Finish Old Jack's quest The Rider and the Gravekeeper takes you on the hard ride, for a Burning Grave Candle that Old Jack sells once he counts you a Regular. There the Horseman waits behind five waves of Jack Skeletons and Jack Archers, pumpkin-headed skeletons with bows, and more waves rise to help him as his health falls. He has about twice the health, hits harder and sets the ground alight from his first volley. No health packs drop for you on this ride.

Every clear leaves a chest where he falls. It pays Hallow Sweets, Festival Tokens, Essence of Fire and Ectoplasm, three random finds (four on the hard ride) such as Lantern Bombs, Cursed Geodes, Fire Resistance Potions or Grave Candles, and favor with Old Jack, the Hallowed and Festival Favor. A later clear the same day pays half. Your first win each day adds his daily Claim and the Horseman's Hoard to the chest, with a chance at his armour, a piece of the Flaming Hallowed set or a Grave Candle back. Only the hard ride's Hoard holds his Flaming Breastplate and the Eternal Candle, which opens the normal graveyard without ever burning down.

His fire hurts. Once Old Jack trusts you, he sells a Fire Resistance Potion that takes 35% off fire damage for three minutes, and both Jack Shields ward off some of it too.

## Every season

- Festival Favor, a reputation every season shares, runs up to Exalted and on through Exalted II, III and IV. Old Jack's quests (all but the first) and his Night and Day jobs pay it, and so does every clear of the Horseman's graveyard.
- Festival Tokens, the wallet every season shares, carry over from season to season and spend at the Festival Shelf in each host's shop, on decorations from the game's own festivals. Exalted II and Exalted III open the Goblin Plushie and the Carved Kweebec Figure there.
- Three achievements count keepsakes from different seasons: Season to Season, Round the Year and Seasons of Orbis, which gives the title "Friend of the Seasons".
- Hytale's Anniversary: every January 13 from 2027, being on the server earns that year's anniversary achievement and the title "the Ever-Present".

Server owners switch any event off, or move its days, in `mods/ziggfreedcommon/calendar.json`, and `/zigcalendar status <event>` shows what the server reads.

## With other mods

- **With MMO Skill Tree** (1.7.2+), Hallow's Eve trains skills: Lantern Bombs train Artillery, Old Jack's rewards and the cracked geodes pay skill XP, the Horseman pays Defense XP, his board posts a Skill job every day that pays favor like his own, the Hallowed set adds luck and Artillery damage, the Carving Bench trains Crafting, and Harvest Moon lifts Harvesting and Artillery XP. The pack never needs MMO Skill Tree.
- **With the MMO Skill Bounty Pack** (1.3.0+), the Daily bounty board posts a haunt contract each day of Hallow's Eve, and Old Jack also sells both candles for Life Essence.

Harvest Feast, the next season, comes later this year. What changed in each version is in [patch-notes/](patch-notes/).

## Build

```powershell
.\build.ps1                  # build the zip, and install it if a Mods folder is known
.\build.ps1 -Install:$false  # build only, no copy
.\build.ps1 -ModsDir <path>  # build, then install into that folder
```

Produces `SeasonsOfOrbis-<version>.zip` (forward-slash entries plus explicit directory entries, which the bundled `.lang` files need). The script is cross-platform (`pwsh ./build.ps1` works on macOS/Linux). To have it also copy the zip into your Hytale `Mods/` folder, set `HYTALE_MODS_DIR` once to that folder (or pass `-ModsDir <path>`).
