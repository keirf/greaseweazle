# Greaseweazle Host Tools

*Tools for accessing a floppy drive at the raw flux level.*

![CI Badge][ci-badge]
![Downloads Badge][downloads-badge]
![Version Badge][version-badge]

<img src="https://raw.githubusercontent.com/wiki/keirf/greaseweazle/assets/banner.jpg">

This repository contains the host tools for controlling Greaseweazle:
an [Open Source][designfiles] USB device capable of reading and
writing raw data on nearly any type of floppy disk.

For more info see the following links:

* [Download binaries][Downloads]
* [Purchase a ready-made Greaseweazle][rmb]
* [Read the GitHub wiki](https://github.com/keirf/greaseweazle/wiki)
* [Greaseweazle firmware repository][firmware]

## Installation

**Windows:** Simply [download][Downloads] and unzip the latest release
of the host tools. You can now open a CMD window and run the `gw.exe` tool
from inside the unzipped release folder.

**macOS, Linux:** First you must install Python v3.7 or later. You can then
install the latest host tools release directly from GitHub using Python Pip:
```
$ python3 -m pip install git+https://github.com/keirf/greaseweazle@latest
```
See the [software installation wiki page][siwp] for more detailed
installation instructions for your platform.

## Usage

Type `gw --help` for on-line help.

Read the [GitHub wiki](https://github.com/keirf/greaseweazle/wiki)
for more detailed usage instructions.

## Redistribution

Greaseweazle source code, and all binary releases, are freely redistributable
in any form. Please see the [license](COPYING).

[designfiles]: https://github.com/keirf/greaseweazle/wiki/Design-Files
[firmware]: https://github.com/keirf/greaseweazle-firmware
[rmb]: https://github.com/keirf/greaseweazle/wiki/Ready-Made-Boards
[Downloads]: https://github.com/keirf/greaseweazle/wiki/Download-Host-Tools
[siwp]: https://github.com/keirf/greaseweazle/wiki/Software-Installation

[ci-badge]: https://github.com/keirf/greaseweazle/workflows/CI/badge.svg
[downloads-badge]: https://img.shields.io/github/downloads/keirf/greaseweazle/total
[version-badge]: https://img.shields.io/github/v/release/keirf/greaseweazle
