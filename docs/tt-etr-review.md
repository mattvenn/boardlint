# Test run: Tiny Tapeout ETR demo board and its carriers

This review was produced by Claude (Anthropic's AI model) with boardlint on 2026-11-25. Nothing
here has been checked on hardware, and the boards' designers have not seen it.

The Tiny Tapeout ETR system is two boards. The baseboard is the demo board
(<https://github.com/TinyTapeout/tt-demo-pcb> at `bbf3dd1`, version 3: RP2350B, USB-C, a 3.3 V
regulator, DIP switches, a seven-segment display, Pmod headers). The chip sits on a carrier
(<https://github.com/TinyTapeout/breakout-pcb> at `91a2bf1`) that plugs onto it through two Hirose
DF12 board-to-board connectors, 60 and 50 contacts at 0.5 mm pitch. Three carriers were checked:
`breakout-sky-qfn` (sky130), `breakout-ihp-qfn` (IHP SG13G2) and `breakout-gf-cob` (GF180MCU,
chip on board). All are KiCad 9, four layers, and the board files define their stack-up.

boardlint could not check two boards as one system before this run. `boardlint mate` was written
for it:

```bash
boardlint mate tt-demo-pcb breakout-pcb/breakout-ihp-qfn -f md -o report.md
```

Full output for each pairing: [sky](examples/tt-etr-demoboard-with-sky-qfn-report.md),
[IHP](examples/tt-etr-demoboard-with-ihp-qfn-report.md),
[GF](examples/tt-etr-demoboard-with-gf-cob-report.md).

```
tinytapeout-demo + breakout-sky-qfn: 0 errors, 3 warnings, 16 notes
tinytapeout-demo + breakout-ihp-qfn: 0 errors, 4 warnings, 16 notes
tinytapeout-demo + breakout-gf-cob:  0 errors, 3 warnings, 15 notes
```

## The connector between the two boards

This is where a two-board design usually goes wrong: a footprint mirrored, a row swapped, two
signals crossed. On all three carriers it is right.

| Check | Result |
|---|---|
| Pads line up | All 112 pads of the carrier's two connectors land on pads of the baseboard's footprint, with a shift only: no turn and no mirror. The carrier's connectors are on its bottom side and the baseboard's on its top, which is what a carrier sitting face up needs. Largest offset 0.05 mm |
| Ground against ground | 29 contacts |
| Supplies | 3.3 V meets 3.3 V on three contacts and USB 5 V meets the carrier's +5V on two. No rail meets ground or a different rail |
| Digital buses | `ui_in`, `uo_out`, `uio` (8 bits each) and the eight `mng` lines meet the same bit number on every carrier |
| Control lines | Project clock, project reset, and the multiplexer's enable, increment and reset each meet the pin of the same function. The Tiny Tapeout 07 breakout had increment and reset crossed (its README says so); these do not |

Pads are paired by where they are, not by their numbers, because a board-to-board connector joins
the contacts that are above one another whatever the two footprints call them.

Things worth knowing, none of them faults:

- **The reserved lines are numbered one apart.** Baseboard `RES0` to `RES2` meet carrier `RES1` to
  `RES3`; baseboard `res3` and `res4` meet carrier `reserved3` and `reserved4`. The copper is
  one-to-one. Only the names differ, which matters to anyone writing firmware from one schematic.
- **Unused analog lines are grounded by the carrier.** The baseboard brings out 22 analog lines
  (A to X). The sky carrier uses 12 and grounds 8; the IHP carrier uses 16 and grounds 6; the GF
  carrier uses all 22. Nothing on the baseboard drives those lines, so grounding them is harmless,
  but a signal fed into, say, header pin A reaches ground on a sky or IHP carrier.
- **`res_extra`** (carrier contact 60 of the 60-way connector) has no pad connection on the baseboard.
- **The sky carrier calls the project reset `p_rst`**, without the bar; the other two and the
  baseboard mark it active low. Naming only.

## Findings

| | Finding | Evidence | Assessment |
|---|---|---|---|
| 1 | `power.unpowered` (IHP carrier): the chip's two `VAA_Analog` pins are on a net that nothing fitted feeds | The only paths to `VAA` are the 0 Ω link R9 and header J1 pin 6, and both are marked do-not-populate. The production bill of materials for v1.2 in `pcb-files` lists R3, R4, R6, R7, R8 and not R9. The GF carrier, drawn the same way, fits R9 | Real as built, unless it is intended: either IHP projects do not use the analog supply, or it is meant to be fed from outside through J1. Worth one sentence in the documentation either way |
| 2 | `bom.value_mpn` (baseboard): crystal load capacitors C30 and C32 say 14 pF; their part number `CC0402CRNPO9BN4R0` is 4 pF | The production bill of materials lists them as 4 pF. The crystal is specified for a 7 pF load: 4 pF each gives about 6 pF with stray, which is right; 14 pF each would give about 11 pF | The board as built is right and the schematic's value field is wrong. boardlint first reported the crystal as mis-loaded, because it believed the value field; the check for a value that disagrees with its part number was added because of this |
| 3 | `layout.impedance` (baseboard): the project clock runs 55 mm with no series resistor, then 25 mm more on the sky carrier | From RP2350 GPIO16 through a solder jumper to the connector; 51 Ω line over a plane. The Tiny Tapeout clock page gives a range up to 66.5 MHz | Low confidence: the 2 ns edge is an assumption, and the RP2350's default drive is slower. Worth a look on a scope at the chip if anyone sees double clocking at high rates. A resistor in place of the solder jumper would be the fix |
| 4 | `decoupling.regulator_caps` (baseboard): the 3.3 V regulator U1 has no output capacitor within 10 mm; the nearest of 0.5 µF or more is C4 (22 µF) at 17 mm | Measured from the regulator's tab. The rail carries 42.5 µF in all. The TLV1117LV asks for 1 µF ceramic at its output and is stable with no series resistance | Low confidence; the 10 mm is a rule of thumb. It matters more with the alternate part in the schematic (next row) |
| 5 | The alternate for U1 is not equivalent | The schematic gives AZ1117CH-3.3 as the alternate to the TLV1117LV33. Read from the two datasheets: the AZ1117C needs 10 µF or more at its output, drops 1.3 V at full load against 0.455 V typical, and draws 6 mA against 50 µA | Not a boardlint check; found while writing the part model. With the alternate fitted and USB at the low end of its range (4.4 V), 3.3 V is no longer regulated: 4.4 − 1.3 = 3.1 V |
| 6 | USB data lines: the protection parts D1 and D2 are polymer suppressors that trigger at about 300 V and clamp at about 35 V | From the Eaton 0603ESDA datasheet named in the schematic: 30 V rated, 0.15 pF. Typical figures only | Low capacitance, which is why they are used, but 35 V is far above what an RP2350 pin tolerates. They take the edge off a discharge; they do not clamp to the supply. Not a boardlint check |
| 7 | USB pair is about 117 Ω differential, 1.0 mm length mismatch | 0.2 mm tracks at a 0.5 mm gap over a plane 0.19 mm away, routed as a pair for 67 mm | Note only. The RP2350 is full speed (12 Mbit/s), which tolerates this. It would matter at high speed |
| 8 | Sky carrier: chip pin 21 `resetb` is connected to nothing | Its only connection is the 0 Ω link R6, not fitted | Almost certainly fine: the TT06 to TT08 breakout wires it the same way and those boards work. boardlint first called it an error (a floating reset); the chip's model now says why it is not |

Several part numbers in the schematics point at a different maker's part at the distributor than
the one named: LCSC C5261054 is an HXY "DMG2305UX-7" (gate limit ±12 V where the Diodes Inc. part
is ±8 V), C23380830 is a TECH PUBLIC "AP2112K-3.3", C2836375 is an MSKSEMI part, not Littelfuse.
None of these changes a finding here. They are recorded in the part models.

## What the tool got wrong on these boards, and what changed

| Seen | Cause | Change |
|---|---|---|
| "Reset pin floats" errors on every carrier checked alone | The reset comes from the baseboard | `boardlint mate` joins the two netlists before the electrical checks run |
| "Crystal load is 11 pF, wants 7 pF" | The value field is wrong; the part number is right | `bom.value_mpn`; the crystal check uses the part number's value where it states one |
| "USB pair: 88 mm length mismatch" | The seven-segment display's decimal-point pin is called `DP` and was taken for USB D+ | A bare `DP` or `DM` needs its partner on the same part |
| "Regulator output capacitance 0 F" (an error) | Only capacitors within 10 mm were counted, measured from the small pin and not the tab | Tab pads are read; when the capacitance is on the rail but far away, the finding says how far and is a warning |
| "Board is out of step with the schematic: 40 nets" | Stitching-via footprints, and buses between sheets, which the built-in netlister does not expand | Board-only footprints are ignored; nets that differ only because of buses are a note |
| Crash in `i2c.bus` | The carrier's EEPROM is not fitted | Unfitted parts are skipped |

## What it did not look at

- **The RP2350B, the flash, the op-amp, the Schmitt inverters, the EEPROM and the display have no
  part model yet.** Their datasheet extraction was cut short by a usage limit on the account that
  ran this review. Until they exist, nothing here checks the RP2350's own supplies and its
  switching regulator (inductor, capacitors, the `VREG_AVDD` filter), its strap and QSPI wiring,
  the debounce circuit's thresholds, the op-amp's pinout variant (the part number is the `U`
  pinout), or the segment currents of the display. Two supply nets (`VREG_AVDD`, `VREG_LX`) have
  no known voltage for the same reason.
- **Supply currents.** No part on either board has a current in its model, so regulator load,
  dropout under load, track current and voltage drop in the copper are not judged.
- **The three chip models are not from datasheets.** They are the KiCad symbols plus the rail
  voltages each carrier gives them.
- **The IHP "off by one" branch.** `breakout-pcb` has a branch whose IHP footprint numbers every
  pad one place round, for chips that were packaged that way. Nothing in the design files on
  `main` can show that; it is a fact about the packaged chips.
- **Mechanical fit.** The mating check uses pad positions only: not connector height, board
  outlines, or parts on the baseboard under the carrier.
- Schematic buses are still not expanded, so the schematic and the board are not compared net by net.
