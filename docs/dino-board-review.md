# Test run: DinoLight board

This review was produced by Claude (Anthropic's AI model): it ran boardlint, read each finding, and
wrote the verdicts below. Nothing here has been checked on hardware.

Board: <https://github.com/mo-seph/dino-board> at commit `4da182c` (2026-11-22):
a mosasaurus-shaped ESP32-S3 toy with 21 SK6812 LEDs, an MPR121 touch controller, a LIS2DH12, a LiPo
charger and USB-C. KiCad 10, two layers, 144 parts, routing unfinished. No known issues were given.

Full machine output: [examples/dino-board-report.md](examples/dino-board-report.md) (and `.json`).

```
dinolight: 1 error, 12 warnings, 31 notes        runtime about 2 s including both simulators
schematic and board netlists agree (84 multi-pin nets)
all 7 ICs, 21 LEDs, 3 FETs, the fuse, switches and USB connector matched a part model
```

## What it found, triaged by Claude

The 13 errors and warnings come from 7 root causes.

| # | Finding | Claude's reading | Verdict |
|---|---|---|---|
| 1 | `power.droop` (error) and `power.regulator`: +3V3 falls below the ESP32's 3.0 V minimum at transmit peaks unless the cell is well charged | The RT9080's dropout is 310 mV typ / 530 mV max at 600 mA (datasheet), so about 0.3 V at the module's 355 mA peak. Add the source path (FET, polyfuse, cell: about 0.45 Ω) and the 0.4 mm supply track between U3 and U4, which sit 101 mm apart (about 185 mΩ, estimated from pad distance x 1.4), and the rail is at 3.06 V with the cell at 3.6 V and the LEDs off. With the LEDs fully on as well, or the cell lower, it is under 3.0 V. The numbers that are assumptions (cell resistance, loop bandwidth) are marked; the dropout and the copper are not assumptions. | **Real, and the most important finding.** Options: move the regulator next to the module or widen the 3V3 route; put the 22 µF the module datasheet shows at the module; choose a lower-dropout or buck-boost regulator; cap LED brightness in firmware. |
| 2 | `power.budget`: F1 (1.1 A hold) may carry 1.27 A | 21 LEDs at 43.5 mA maximum plus 355 mA. All-white full brightness while transmitting. The polyfuse model has no datasheet behind it. | Real in the worst case; a firmware brightness limit settles it. Record it as a waiver. |
| 3 | `layout.track_current`: 0.4 mm battery-path tracks for up to 1.27 A | Same worst-case current; IPC-2221 gives 1.23 A at this width. | Real but marginal; the routing is a draft. Pour or widen +BATT and VLED. |
| 4 | `decoupling.per_part` x3: nearest 100 nF is 8 to 11 mm from U5, U6, U7 | Measured pad to pad. U5's datasheet says "as near as possible". | Real placement issues. |
| 5 | `layout.coupling` x3: USB D+/D- run 25 to 33 mm beside touch-electrode tracks, down to 0.6 mm apart (estimated 0.3 to 0.7 pF) | Geometry is from the board. The capacitance is a closed-form estimate. It matters only while USB is active. | Plausible; worth separating when the routing is redone. Low confidence by design. |
| 6 | `power.supply_range` x2: SK6812 specified from 3.7 V, VLED goes to 3.0 V | True. The board's own notes already list this as unverified. | Real, known. |
| 7 | `layout.return_path`: SPINE_DATA has no ground under half its length | True; the pours are incomplete. At 800 kHz the consequence is small. | True, low value. |

So: one finding to act on before ordering (1), four worth fixing during layout (2 to 5) and two
true-but-known (6, 7). An eighth warning in the first run (the USBLC6-2's 5.25 V stand-off voltage
against a 5.5 V VBUS maximum) was a false positive in practice, and the rule now allows a TVS that margin.

None of this has been checked on hardware. Findings 1 to 3 depend on currents that are sums of
datasheet maxima, and 1 also on an assumed cell resistance.

The notes are worth reading too. Among them: the I2C address map (0x19, 0x5A), the charge current
(213 mA), that the first-LED logic level is met in practice but not by the datasheet's guaranteed
numbers, that IO3 floats (only matters with a burnt eFuse), and that the 4.7k pull-ups are too weak
for 400 kHz once a Qwiic cable and module are attached.

## What the simulators said

- **I2C:** both lines idle high; U5 answers at 0x19 and returns its WHO_AM_I value, U7 answers at
  0x5A; a scan of every address finds exactly those two.
- **LED chains:** all 21 LEDs latch data; the spine is D1 to D20 in order; the eye is its own chain.
- **Droop:** four corners, in the report's evidence table.

## Does it catch mistakes? Fault injection

Since the board has no known bugs, 26 were injected one at a time
(`python3 tools/fault_report.py <dino-board>`): each is one edit to the loaded design, and the test
requires a *new* error or warning from the check that should own it.

**26 of 26 are flagged** (28 of 28 since 2026-11-25, when two layout faults were added). On the first run it was 20 of 22: an address clash on a newly added part
and a too-low logic divider were missed, and a crossed I2C device and a P-FET with no gate
pull-down were caught only by unrelated findings. All four led to fixes in the checks. This is a test of the checks against mistakes Claude chose, on the
board they were developed on: it shows the mechanisms work, not what fraction of real mistakes they catch.
The [regression corpus](regression-corpus.md) is the less flattering measure.

| Injected mistake | Flagged by |
|---|---|
| MPR121 SDA and SCL swapped | `i2c.bus`, `sim.i2c` |
| SDA pull-up left off | `i2c.bus`, `sim.i2c` (bus idles at `z`) |
| I2C pull-ups 470R | `i2c.bus` (over 3 mA) |
| LIS2DH12 CS tied low (SPI mode) | `sim.i2c`: the part never answers. The static check only notes it. |
| Second MPR121 with the same strap | `i2c.bus`, `sim.i2c` (two devices acknowledge 0x5A) |
| MPR121 REXT 7.5k for 75k | `pin.requirements` |
| One LED with DIN and DOUT exchanged | `led.chain`, `sim.led_chain` (16 of 21 get no data) |
| LED rail on 5 V with 3.3 V data | `led.chain`, `sim.led_chain` |
| USB D+ / D- swapped | `usb.wiring` |
| CC2 resistor missing; CC1 and CC2 on one resistor; CC resistors 10k | `usb.wiring` |
| USB-serial bridge wired TX to TX | `uart.direction` |
| LDO output capacitor missing | `decoupling.regulator_caps` |
| Charger PROG 1k | `pin.requirements` |
| Divider lets 5 V reach a 3.3 V pin | `power.pin_voltage` |
| Divider too low to read as high | `power.logic_level` |
| EN pull-up missing | `pin.requirements`, `pin.floating_control` |
| Pull-down on strapping pin IO0 | `mcu.strapping` |
| All 100 nF on 3V3 missing | `decoupling.per_part` |
| Regulator fed from 12 V | `power.supply_range` |
| P-FET gate pull-down path missing | `ratings.fets` |
| Regulator enable tied to ground | `pin.floating_control` |
| Battery-sense divider moved to a pin with no ADC | `mcu.pin_use` |
| **Historical:** status dividers 100k/100k, as first drawn | `power.logic_level` |
| **Historical:** regulator capacitors 1 µF 0402, as first drawn | `decoupling.regulator_caps` |

The last two are mistakes this board really had. Its `NOTES.md` records them as found by a design
review and fixed before the first commit; putting the old values back makes boardlint report both.

## What it did not look at

The board's notes list open items the tool has no check for: unrouted connections (DRC's job),
the antenna keep-out, footprint pin-1 and polarity against the assembler's library, connector
polarity of the LiPo lead, LED rail inrush, and the deep-discharge recovery problem its review
found. The last two are the kind of thing a part-model plus simulation approach could reach;
the others need footprint and mechanical data.

---

## Update, 2026-11-25: copper extraction

The linked report was regenerated after boardlint gained a resistor-network extraction of the
routed copper ([copper-extraction.md](copper-extraction.md)), so it now reads 1 error, 16 warnings,
42 notes. The text above describes the first run and is left as it was. What the new checks add on
this commit:

- `layout.ir_drop`: 140 mV (3.9 %) is lost between the reverse-protection transistor Q1 and the LED
  switch Q2 on +BATT at 1269 mA. The earlier estimate could not see a rail fed through a transistor.
- `layout.ir_drop`: the ground pour is in separate pieces, and 27 parts have no copper return path
  to their supply. The board's notes say the same: "79 ground items unconnected".
- `layout.ir_drop`: U7 pin 20 (VDD) and the battery connector's path to fuse F1 have no copper at
  this commit. KiCad's DRC reports these as unrouted; they are listed here because the current
  solve cannot reach them.
- `power.droop` now uses the extracted path from the regulator to the ESP32 module: 156 mΩ and
  94 nH, where the estimate was 185 mΩ and 212 nH. The result is the same error (2.05 V).
- `layout.impedance` (notes): on a two-layer board the USB pair is about 193 Ω differential, far
  from 90 Ω. That is normal for two layers and tolerable at full speed.

# Second run: commit `eb2fd13` (2026-11-23), with the owner's description to check against

Two commits arrived after the first run: five sensors and a buzzer, 18 spine LEDs instead of 20, and
a top-emitting eye LED. The owner then described what should be on each MCU pin and each I2C
address. That turns this run into a comparison: does the tool derive the same picture from the files?

Run with `--netlist-from sch`, because this commit's board file is behind its schematic (its own
commit message says so). Output: [examples/dino-board-eb2fd13-report.md](examples/dino-board-eb2fd13-report.md).

```
dinolight: 1 error, 18 warnings, 30 notes
```

## The owner's description against what was derived

| Owner's description | Derived from the files | Agrees |
|---|---|---|
| I2C on GPIO41 SDA, GPIO42 SCL, 2.2k pull-ups | `mcu.pin_use`: IO41 = SDA, IO42 = SCL; `i2c.bus`: 2.2k on each | yes |
| 0x29 light, 0x2C compass, 0x44 temperature, 0x46 pressure, 0x5C touch, 0x6A motion | `i2c.bus` address map: the same six. Three come from straps: MPR121 ADDR is on SDA (0x5C), BMP580 SDO on ground (0x46), LSM6DS3 SA0 on ground (0x6A) | yes |
| | `sim.i2c`: the five targets with a simulation model answer at those addresses and return their ID registers (SHT40 is command-based and has no model) | |
| Spine LEDs on GPIO11 through 330R; eye LED on GPIO48 through 330R | `led.chain`: 18 LEDs D1 to D18 from IO11 through R14 330R; D21 from IO48 through R15 330R. `sim.led_chain`: 19 of 19 latch data, spine in order | yes |
| USB on GPIO19, GPIO20 | USB_D- and USB_D+ (the module's pins 23, 24) to J1 | yes |
| UART0 on GPIO43, GPIO44, test points only | TXD0, RXD0: test point only | yes |
| No SPI; motion and pressure sensors strapped to I2C | no SPI bus found; LSM6DS3 CS and BMP580 CSB are on 3V3, and the simulation models only answer on I2C with those pins high | yes |
| Interrupts: touch GPIO1, motion GPIO15, GPIO16 | IO1, IO15, IO16: interrupt inputs, all wake-capable (RTC) pins | yes |
| Buzzer on GPIO4 | IO4: digital out to a FET gate (Q4, which switches BZ1) | yes |
| Battery voltage: analogue on GPIO10 | IO10: analog in, +BATT through R6/R7, on ADC1 (the ADC that works with the radio on) | yes |
| Charge status GPIO17, USB-present GPIO18: digital | IO17, IO18: digital inputs through dividers. Both pins are ADC2-only, which is fine for digital use | yes |
| LED rail enable GPIO21 | IO21: digital out to a FET gate | yes |
| "ESP32-S2-MINI-1" | The schematic's U4 is **ESP32-S3-MINI-1-N8** (and GPIO48 does not exist on the S2 module) | **no**: the description, not the board, looks wrong |

Reset: EN has a 100k pull-up and 100 nF (10 ms), is pulled low by the TLV803S supervisor through
1k, and has a button. No crystal or oscillator is on the board (the module has its own), so
`clock.source` has nothing to say.

## New in this revision

- **`sync.schematic_board` (warning):** 7 nets differ; D21's footprint differs (schematic
  `LED_SK6812MINI-012_3.7x3.5mm`, board still the reverse-mount MINI-E); C29, C30, D19, D20 are on
  the board only. Expected mid-change, and the reason every layout finding in this run describes
  the old routing. One thing to carry into the re-route: the MINI-012's pin order is not the
  MINI-E's (1 DIN, 2 VDD, 3 DOUT, 4 GND against 1 GND, 2 DIN, 3 VDD, 4 DOUT), so the old pad nets
  must not survive.
- **`load.inductive` (warning):** the buzzer gets about 0.63 V. R35 and R37 in parallel (50 Ω)
  in series with a 12 Ω coil from 3.3 V; the part is specified from 2 V. The board's notes
  already call the loudness "an estimate", and the resistors are there on purpose (they cap the
  current if the pin sticks high). This puts a number on it. The flyback diode D24 is present and
  the right way round.
- Unchanged from the first run: the 3.3 V rail under transmit peaks (finding 1), the fuse and
  track current worst case, and SK6812 operation below 3.7 V.

Nothing in the owner's description was contradicted by the board except the module's name.
