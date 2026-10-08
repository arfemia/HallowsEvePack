# Seasons of Orbis

Yearly events for your Hytale server, starting with Hallow's Eve. Every October, Old Jack lights the lanterns in the Forgotten Temple, and the dead come out after dark.

Hallow's Eve starts on its own on October 1 and runs to November 3, every year. You need Ziggfreed's CommonLib 2.2.0 or newer and RPG Stations 1.1.0 or newer. MMO Skill Tree is optional: with it, the season trains your skills as well.

[![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/5NFdZsUxHZ) [![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/ziggfreed) [![Documentation](https://img.shields.io/badge/Docs-Read%20More-0ea5e9?style=for-the-badge)](https://mmo-skill-tree-docs.ziggfreed.com)

---

[![Host your own Hytale server with Kinetic Hosting](https://i.imgur.com/UHn3FzW.png)](https://billing.kinetichosting.com/aff.php?aff=1262)

---

## What it adds

- **Old Jack**, a pumpkin-headed host who sets up in the Forgotten Temple for the season. His six quests end with lighting the Hollow Lantern, a keepsake with the year on it, and that last quest comes back every October.
- Three dailies, plus Old Jack's board: a job for the dark and a job for the daylight, every day. Earn his favor and a second of each opens up. Jobs pay the moment you finish.
- Two reputations, Old Jack's Favor and the Hallowed. Old Jack's runs from Stranger up to Jack's Own. The Hallowed keep counting past Exalted and leave you a cache every so often. His quests and board jobs pay into both, and putting down the night's creatures raises the Hallowed. The Jack Helm and the Jack Shield add favor while you wear them. Favor carries over to next year.
- Old Jack warms up to you. He greets you by your rank once a day and pays a little favor for the visit. Once he trusts you, he sells you the Jack Shield, and at Confidant you earn Jack's Confidant and its title.
- Hallow Sweets, the season's money. Spend them at Old Jack's stall on Lantern Bombs, lanterns, the Jack Helm and a Costume Wand. Whatever you don't spend keeps until next year.
- A shelf of Halloween decorations at the stall too: lights, two carved pumpkins (one scary, one cute), a straw basket, a scarecrow and a wagon.
- Trick or treat. Once a day, knock on any character who has a conversation for you. With MMO Skill Tree or another pack that gives characters conversations, every one of them plays along; on this pack alone, only Old Jack does. You always get a few sweets, then maybe more, some candy canes, a pumpkin pie, or a costume.
- After dark, away from torches, Jack Skeletons, Hollow Ghouls and Lost Souls come out, and Geode Wraiths walk the mineshafts. By dawn they are gone.
- **Lantern Bombs**: carved pumpkins packed with black powder, in four tiers. Each one hits harder and wider than the last. The Burning Lantern Bomb sets things on fire. Go a tier up and they slow down too, and the Shattering Lantern Bomb throws flaming shards on top. A blast never hurts a player.
- The Hallowed set, the Jack Helm and the Jack Shield. Helm on and shield in your off hand gives you more health and less fire damage. You glow like a lantern, too.
- A Costume Wand. Turn a friend into a Jack Skeleton or a Lost Soul for a few minutes. They can take it off whenever they like.
- Cursed Geodes turn up while you mine. Crack one for crystals and something extra. Pumpkins you pick by hand sometimes come up Hallowed.
- The Carving Bench. Craft it at a Workbench, then carve lanterns, the Jack Helm and Lantern Bombs on it all year. The Jack Shield only carves during the event.
- Harvest Moon, the last three days of October. About twice the creatures come out at night, and every geode and Hallowed Pumpkin you find comes in pairs. Old Jack puts a bundle of bombs on the stall.
- Seven achievements a season. The last one, The Hallowed, is for earning the other six in one season and gives you the title "the Hallowed". Each year's achievements stay with you as feats.
- Keepsakes that build over the years. Old Friend wants three Hallow's Eves. Light the Hollow Lantern in three seasons for Lantern Keeper and the title "Keeper of Lanterns". First Lanterns only goes to players who light it in 2026, the first year.
- An Almanac page for the season, opening on a banner built from its own items: your keepsakes, and lifetime counts of bombs thrown, ghouls felled, Jack Skeletons knocked down, souls freed, geodes cracked and Geode Wraiths put down.
- Translated into 9 languages.

## How it works

1. Log in any time from October 1 to November 3. A banner tells you Old Jack is waiting at the Forgotten Temple, and a quest in your log, Lanterns in the Temple, sends you to find him.
2. Find him there and press F. He hands out the questline, and his conversation opens his board and his stall. Ask him for the Almanac to see your season, or how you stand with him.
3. Go out after dark, away from torches. The creatures his quests and board send you after drop the bombs, Ectoplasm and pumpkins you will want.
4. Spend your sweets at the stall, or carve what you need at a Carving Bench.
5. On November 3 the event ends and Old Jack leaves. Everything you earned stays with you, and a quest you had not finished waits for him to come back next October.

## With MMO Skill Tree

Install MMO Skill Tree 1.7.0 or newer beside this pack and the season also trains skills. Lantern Bombs train Artillery. Old Jack's quests, his board jobs and the season's achievements pay XP in the skill the work trains: Defense for the fights, Harvesting for the pumpkins, Mining for the geodes and Artillery for the bombs. The Hallowed and Jack's Guest each add an XP boost token, cracked geodes pay Mining XP, and his board posts a Skill job every day, which pays favor like his own. The Hallowed set adds luck and Artillery damage, the Carving Bench trains Crafting, and while Harvest Moon is up, Harvesting and Artillery XP get a lift for everyone. The pack never needs MMO Skill Tree: without it, those rewards don't show and the rest of the season plays the same.

Add the MMO Skill Bounty Pack 1.3.0 or newer and its Daily bounty board posts a haunt contract each day of the event, paying a few Hallow Sweets on top of its tokens and XP.

## For server owners

- Nothing to place. The event starts and ends by the date (UTC), and Old Jack sets himself up in the temple.
- To switch Hallow's Eve off, add `"Hallows_Eve": { "Enabled": false }` to `mods/ziggfreedcommon/calendar.json` and run `/zigcalendar reload`. Harvest Moon has its own switch under `"Harvest_Moon"`, and the same file can move either event's days.
- Off means gone. Old Jack, his stall and board, his quests, the trick-or-treat line and the sweets in the wallet strip all disappear, and no new creatures spawn (any still out leave at dawn). Nothing anyone earned is lost, and it all comes back when the event does.
- The items keep working all year once someone has them.
- `/zigcalendar status Hallows_Eve` shows what the server reads.
- The Almanac page's banner is laid out from the season's items. You can rearrange it, or swap in a picture of your own, in `mods/ziggfreedcommon/almanac.json`; whatever you leave out stays as the pack has it.
- The creatures are as tough as the game's own: a Hollow Ghoul hits like a Ghoul, and they come out in the first zone too. They are not Memories.

## Install

1. Install Ziggfreed's CommonLib (2.2.0 or newer) and RPG Stations (1.1.0 or newer).
2. Drop `SeasonsOfOrbis-1.0.0.zip` into your server's `Mods/` folder beside them.
3. Start the server. During the event, Old Jack is in the Forgotten Temple.

## Roadmap

- The Hallow King and his Hollow Crypt, in a later update.

## Versions

### [Full Changelog](https://github.com/arfemia/HallowsEvePack/tree/main/patch-notes)

### v1.0.0 (unreleased, held)

First release: Old Jack's questline, dailies, board and stall (Halloween decorations included), favor with Old Jack and the Hallowed, trick-or-treat, the creatures of the season, Lantern Bombs, the Hallowed set, the Costume Wand, Cursed Geodes, the Carving Bench, Harvest Moon, seven achievements a season with a title, three keepsakes across the years with another, and an Almanac page. Needs Ziggfreed's CommonLib 2.2.0 and RPG Stations 1.1.0.

## Links & Support

[![MMO Skill Tree](https://img.shields.io/badge/CurseForge-MMO%20Skill%20Tree-F16436?style=for-the-badge&logo=curseforge&logoColor=white)](https://www.curseforge.com/hytale/mods/mmo-skill-tree) [![Get Pro Edition](https://img.shields.io/badge/Get%20Pro%20Edition-F59E0B?style=for-the-badge)](https://mmo-skill-tree-docs.ziggfreed.com/commercial)

- [Ziggfreed's CommonLib](https://www.curseforge.com/hytale/mods/ziggfreeds-commonlib) (required)
- [RPG Stations](https://www.curseforge.com/hytale/mods/rpg-stations) (required)
- [MMO Skill Tree](https://www.curseforge.com/hytale/mods/mmo-skill-tree) (optional)
- [MMO Skill Bounty Pack](https://www.curseforge.com/hytale/mods/mmo-skill-tree-bounty-board-pack-rich-customizable)
- [Documentation](https://mmo-skill-tree-docs.ziggfreed.com)
- [Discord](https://discord.gg/5NFdZsUxHZ)

Questions or suggestions? Join the [Discord](https://discord.gg/5NFdZsUxHZ) or leave a comment.

**Support Development:** [Ko-fi](https://ko-fi.com/ziggfreed)

_Seasons of Orbis is not affiliated with Hypixel Studios or Hytale._
