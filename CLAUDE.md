# Hallow's Eve Pack

The yearly Hallow's Eve event. The family-wide rules apply here; this file adds only what is specific to this pack.

- zc-only: the manifest hard-depends on ZiggfreedCommon alone, with RPG Stations optional. Author only zc vocabulary and installed vanilla ids here; never an MMO id, kind or factor.
- The MMO layer ships in the MMO jar under a `Hallows_Eve` subtree, as additive contributions (`ContributesTo`, extensions); a same-id override only where a contribution cannot express it.
- Ids are prefixed `Hallows_Eve_`; quests and achievements sit under `_Hallows_Eve` folders.
- The pack carries its own nine-locale lang files.
- Anything that needs RPG Stations (the Carving Bench) must leave the pack booting cleanly when RPG Stations is absent.
- Everything event-only is gated on zc-calendar (`ziggfreedcommon:calendar_live`) and vanishes when the event or its kill switch is off; the items stay plain native assets.
