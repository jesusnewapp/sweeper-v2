# Open-source ROM players

Sweeper V2 does not bundle or automatically install emulator binaries. Choose a
player from its official project page, verify the download using the project's
published guidance, and use only ROMs and firmware you have the rights to use.
An emulator's open-source license does not grant rights to game content.

| Player | Useful for | Platforms | Official download | License |
|---|---|---|---|---|
| RetroArch | Multi-system frontend using separately licensed cores | Windows, macOS, Linux and others | [retroarch.com](https://www.retroarch.com/?page=platforms) | [GPL-3.0](https://github.com/libretro/RetroArch/blob/master/COPYING) |
| MAME | Arcade machines and other historical systems | Windows, macOS, Linux | [mamedev.org](https://www.mamedev.org/release.html) | [GPL-2.0+ project license](https://docs.mamedev.org/license.html) |
| mGBA | Game Boy, Game Boy Color and Game Boy Advance | Windows, macOS, Linux | [mgba.io](https://mgba.io/downloads.html) | [MPL-2.0](https://github.com/mgba-emu/mgba/blob/master/LICENSE) |
| Dolphin | GameCube and Wii | Windows, macOS, Linux, Android | [dolphin-emu.org](https://dolphin-emu.org/download/) | [GPL-2.0+](https://github.com/dolphin-emu/dolphin/blob/master/COPYING) |

## Suggested workflow

1. Run the rights-free ROM preset and retain accepted files in staging.
2. Review each item's rights record and SHA-256 result.
3. Select a player matching the manifest's `metadata.platform` value.
4. Obtain any required firmware only from an authorized source.
5. Test from a copy of the staged object; do not alter the content-addressed original.

These links are informational. Projects, supported systems, downloads, and
licenses can change; check the official page before installing or distributing.
