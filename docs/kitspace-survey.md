# Survey: fix commits in Kitspace projects

This survey was done by Claude (Anthropic's AI model). It looks for real hardware mistakes, recorded
in git history, in the open-source boards listed by [Kitspace](https://github.com/kitspace/kitspace),
to use as test material for boardlint. Nothing here was checked on hardware.

## What was done

1. The project list was taken from `boards.txt` in the Kitspace registry repository (commit
   `0c3c058`, 2025-02-18): 150 repositories. The Kitspace website was not used.
2. 144 of them could be cloned. Only history and file names were fetched at this stage.
3. `tools/kitspace_scan.py` read each log for commits whose subject looks like a fix (fix, wrong,
   swapped, pull-up, polarity, pinout, footprint, ...) and that touch a schematic or board file. It
   also searched READMEs for errata sections.
4. Claude picked 33 of the clearest commits, plus one README erratum, and ran boardlint on the
   revision before and after each. A fix counts as caught when a relevant finding exists before
   and is gone after.

"Most popular" could not be judged by GitHub stars: the session had no API access to those
repositories. Commit and author counts were used to pick well-used projects.

## What is in the registry

| | Repositories |
|---|---|
| Listed | 150 |
| Cloned | 144 |
| KiCad 5 (legacy `.sch`) with a board file | 74 |
| KiCad 6 or later (`.kicad_sch`) | 26 |
| Eagle | 23 |
| KiCad board file only | 2 |
| Other or no board files found | 19 |

68 repositories have at least one candidate fix commit. 31 KiCad repositories have a strongly
worded one (217 commits in all). Three READMEs have errata text.

The richest histories, for later mining:

| Project | Format | Commits | Authors | Strong candidates |
|---|---|---|---|---|
| [emard/ulx3s](https://github.com/emard/ulx3s) | KiCad 5 | 2732 | 8 | 58 |
| [intergalaktik/ulx4m](https://github.com/intergalaktik/ulx4m) | KiCad 6+ | 2816 | 9 | 60 (shares history with ulx3s) |
| [GlasgowEmbedded/glasgow](https://github.com/GlasgowEmbedded/glasgow) | KiCad 6+ | 3145 | 109 | 24 |
| [eez-open/modular-psu](https://github.com/eez-open/modular-psu) | KiCad 6+ (older boards in Eagle) | 434 | 16 | 7 |
| [joeycastillo/The-Open-Book](https://github.com/joeycastillo/The-Open-Book) | KiCad 6+ (older boards in Eagle) | 261 | 9 | 7 |
| [BeeHive-org/BeeHive](https://github.com/BeeHive-org/BeeHive) | KiCad 6+ | 421 | 9 | 7 |
| [hutscape/oak](https://github.com/hutscape/oak) | KiCad 6+ | 424 | 3 | 6 |
| [sci-bots/dropbot-control-board.kicad](https://github.com/sci-bots/dropbot-control-board.kicad) | KiCad 5 | 74 | 2 | 6 |
| [fossasia/pslab-hardware](https://github.com/fossasia/pslab-hardware) | KiCad 6+ | 303 | 12 | 3 |
| [rbaron/b-parasite](https://github.com/rbaron/b-parasite) | KiCad 6+ | 472 | 24 | 3 |

## Result on 34 fixes

boardlint ran on all 68 revisions without a crash. On the first, blind run it flagged **1 of 33**
commits. After one check was added for the README erratum, the count is **2 of 34**.

| Outcome | Fixes | Meaning |
|---|---|---|
| Caught | 2 | A relevant finding before the fix, gone after it |
| Visible, not flagged | 13 | boardlint sees the wiring change but has no rule or no part model that judges it |
| Not visible | 12 | boardlint sees no difference between the two revisions |
| Not KiCad | 6 | The commit changed Eagle files |
| Not run | 1 | The commit spans several boards and the right one was not picked |

This is the unbiased number the [regression corpus](regression-corpus.md) lacked, and it is low.
The reasons are specific, and most of them are the same two.

### Caught

| Project | Fix | Bug | Flagged by |
|---|---|---|---|
| [The-Open-Book](https://github.com/joeycastillo/The-Open-Book/commit/6bb483f92) | `6bb483f` | No pull-up on the ESP32-S3 EN pin | `pin.floating_control`, on the blind run |
| [teensy-audio-fx](https://github.com/mattvenn/teensy-audio-fx/tree/99c1038) | V1 at `99c1038` against the current head | LRCLK and BCLK swapped at the audio codec (README errata) | `net.name_mismatch`, a check added because of this case |

### Visible, not flagged

| Project | Fix | Bug | What is missing |
|---|---|---|---|
| [b-parasite](https://github.com/rbaron/b-parasite/commit/7f652ce75) | `7f652ce` | Wrong symbol and footprint for the MMBT3906 transistor | The part's pinout in a model, to compare with the symbol |
| [glasgow](https://github.com/GlasgowEmbedded/glasgow/commit/eef7829a7) | `eef7829` | Electrostatic discharge (ESD) protection array on the wrong footprint | The package pinout in a model |
| [glasgow](https://github.com/GlasgowEmbedded/glasgow/commit/e741c1703) | `e741c17` | USB lines crossed at an ESD array | A model of that part (its pins are named D1, D2) |
| [esp8266-breakout](https://github.com/mattvenn/esp8266-breakout/commit/f06ae5354) | `f06ae53` | GPIO4 and GPIO5 crossed on an ESP8266 module | A model of the module |
| [glasgow](https://github.com/GlasgowEmbedded/glasgow/commit/56c17893c) | `56c1789` | Pull-up added on the SYNC pin | A model saying the pin is open-drain |
| [ulx4m](https://github.com/intergalaktik/ulx4m/commit/af1738a25) | `af1738a` | Pull-ups added on ID and power-enable lines | Models of the parts |
| [Otter-Iron](https://github.com/Jana-Marie/Otter-Iron/commit/f14b43227) | `f14b432` | Pull-up added on a connector signal | A model of what plugs in |
| [key-ripper](https://github.com/bschwind/key-ripper/commit/7b0be4335) | `7b0be43` | Pull-up added on the RP2040 RUN pin | Nothing: RUN has an internal pull-up, so by the datasheet this is an improvement and not a bug |
| [ulx4m](https://github.com/intergalaktik/ulx4m/commit/8ac8e2602) | `8ac8e26` | Ethernet receive clock moved to a different FPGA clock pin | Clock-region data for the FPGA and pin roles for the Ethernet PHY |
| [DynamixelShield](https://github.com/descampsa/DynamixelShield/commit/566f4b8b4) | `566f4b8` | Fuse moved ahead of the reverse-polarity protection | A rule about the order of parts in the power path |
| [dropbot-40-channel](https://github.com/sci-bots/dropbot-40-channel-HV-switching-board.kicad/commit/d65afd769) | `d65afd7` | Decoupling capacitor added for a logic IC | The generic rule asks for one capacitor per rail, not one per IC |
| [darling](https://github.com/xengi/darling/commit/9928be50f) | `9928be5` | USB-C made reversible | A rule for it on this connector's symbol |
| [Neotron-32](https://github.com/Neotron-Compute/Neotron-32-Hardware/commit/73d67f428) | `73d67f4` | 5 V on the 3.3 V plane at a header | Connector pinouts are outside the design files |

### Not visible

Ten of these twelve are commits that change only a KiCad 5 schematic. boardlint does not netlist
KiCad 5 schematics: it takes nets from the board file, which those commits did not touch.

| Project | Fix | Bug |
|---|---|---|
| [oak](https://github.com/hutscape/oak/commit/e68675ad1) | `e68675a` | SPI conflict solved with a pull-down |
| [oak](https://github.com/hutscape/oak/commit/460f1581b) | `460f158` | Pull-up and pull-down added for the SPI clock |
| [oak](https://github.com/hutscape/oak/commit/5cf03c8d2) | `5cf03c8` | Decoupling capacitors added, net labels fixed |
| [pslab-hardware](https://github.com/fossasia/pslab-hardware/commit/af41b3aa5) | `af41b3a` | Pull-ups added on two SPI chip selects |
| [ulx3s](https://github.com/emard/ulx3s/commit/19d34652d) | `19d3465` | Two Wi-Fi module GPIOs swapped |
| [ulx3s](https://github.com/emard/ulx3s/commit/10e0b9c17) | `10e0b9c` | Zener diode wrongly placed |
| [ulx3s](https://github.com/emard/ulx3s/commit/4965879df) | `4965879` | LED moved to 3.3 V so it is off by default |
| [dropbot-40-channel](https://github.com/sci-bots/dropbot-40-channel-HV-switching-board.kicad/commit/fdaa8f8d8) | `fdaa8f8` | High voltage and ground swapped on BNC jacks |
| [dropbot-control-board](https://github.com/sci-bots/dropbot-control-board.kicad/commit/bbafe168e) | `bbafe16` | I2C pull-ups lowered from 4.75 kΩ to 2 kΩ |
| [less-smog](https://github.com/less-smog/hardware/commit/b7c0bf8bb) | `b7c0bf8` | Pinout reverted: hardware SPI was not available on the chosen pins |
| [glasgow](https://github.com/GlasgowEmbedded/glasgow/commit/4500338ba) | `4500338` | Regulator enable pull-downs changed from 100 kΩ to 10 kΩ (a value, not a connection) |
| [b-parasite](https://github.com/rbaron/b-parasite/commit/d3ed9a331) | `d3ed9a3` | Phototransistor footprint geometry |

## What to build from this

1. **A KiCad 5 schematic netlister.** 74 of the 100 KiCad projects in the registry are KiCad 5, and
   ten of the twelve invisible fixes are schematic-only commits in them. This is the largest
   single gain, and it also makes KiCad 5 projects checkable before a board exists.
2. **Pinouts in part models.** Four fixes are a symbol or footprint that does not match the part
   (a transistor, two ESD arrays, a Wi-Fi module). A model that lists pin number, name and
   package would let `footprint.pin_map` compare against the part, not only symbol against footprint.
3. **More part models in general.** Five fixes add a pull-up that only a datasheet says is needed.
4. **Rules on values, not only connections.** Two fixes change a resistor value.
5. **A second pass over the big histories.** ulx3s and Glasgow alone have about 80 more
   strongly-worded candidates that were not examined.

## Limits of this survey

- Commits were found by their subject line. A fix described only in the body, or not described,
  is missed, and some matches are not hardware bugs.
- Only 34 of 217 strong candidates were examined, chosen by Claude for clarity, so the sample is
  not random.
- "Caught" was judged by Claude reading the findings that differ, not by an independent reviewer.
- Six of the commits picked turned out to change Eagle files; the scan matched their `.sch` extension.

## Reproducing it

The candidate list, with the fix commit, the directory and the outcome for each, is
`tests/corpus_kitspace.yaml`. The scanner is `tools/kitspace_scan.py`. Nothing from the surveyed
repositories is stored in this one.
