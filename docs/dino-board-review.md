# Test run: DinoLight board

Board: <https://github.com/mo-seph/dino-board> at commit `4da182c` (2026-11-22):
a mosasaurus-shaped ESP32-S3 toy with 21 SK6812 LEDs, an MPR121 touch controller, a LIS2DH12, a LiPo
charger and USB-C. KiCad 10, two layers, 144 parts, routing unfinished. No known issues were given.

Full machine output: [examples/dino-board-report.md](examples/dino-board-report.md) (and `.json`).

```
dinolight: 1 error, 12 warnings, 31 notes        runtime about 2 s including both simulators
schematic and board netlists agree (84 multi-pin nets)
all 7 ICs, 21 LEDs, 3 FETs, the fuse, switches and USB connector matched a part model
```

## What it found, triaged by hand

The 13 errors and warnings come from 7 root causes.

| # | Finding | My reading | Verdict |
|---|---|---|---|
| 1 | `power.droop` (error) and `power.regulator`: +3V3 falls below the ESP32's 3.0 V minimum at transmit peaks unless the cell is well charged | The RT9080's dropout is 310 mV typ / 530 mV max at 600 mA (datasheet), so about 0.3 V at the module's 355 mA peak. Add the source path (FET, polyfuse, cell: about 0.45 ohm) and 100 mm of 0.4 mm track from U3 at the tail end to U4 (about 185 mohm), and the rail is at 3.06 V with the cell at 3.6 V and the LEDs off. With the LEDs fully on as well, or the cell lower, it is under 3.0 V. The numbers that are assumptions (cell resistance, loop bandwidth) are marked; the dropout and the copper are not assumptions. | **Real, and the most important finding.** Options: move the regulator next to the module or widen the 3V3 route; put the 22 uF the module datasheet shows at the module; choose a lower-dropout or buck-boost regulator; cap LED brightness in firmware. |
| 2 | `power.budget`: F1 (1.1 A hold) may carry 1.27 A | 21 LEDs at 43.5 mA maximum plus 355 mA. All-white full brightness while transmitting. The polyfuse model has no datasheet behind it. | Real in the worst case; a firmware brightness limit settles it. Record it as a waiver. |
| 3 | `layout.track_current`: 0.4 mm battery-path tracks for up to 1.27 A | Same worst-case current; IPC-2221 gives 1.23 A at this width. | Real but marginal; the routing is a draft. Pour or widen +BATT and VLED. |
| 4 | `decoupling.per_part` x3: nearest 100 nF is 8 to 11 mm from U5, U6, U7 | Measured pad to pad. U5's datasheet says "as near as possible". | Real placement issues. |
| 5 | `layout.coupling` x3: USB D+/D- run 25 to 33 mm beside touch-electrode tracks, down to 0.6 mm apart (estimated 0.3 to 0.7 pF) | Geometry is from the board. The capacitance is a closed-form estimate. It matters only while USB is active. | Plausible; worth separating when the routing is redone. Low confidence by design. |
| 6 | `power.supply_range` x2: SK6812 specified from 3.7 V, VLED goes to 3.0 V | True. The board's own notes already list this as unverified. | Real, known. |
| 7 | `layout.return_path`: SPINE_DATA has no ground under half its length | True; the pours are incomplete. At 800 kHz the consequence is small. | True, low value. |

So: one finding I would act on before ordering (1), four worth fixing during layout (2 to 5) and two
true-but-known (6, 7). An eighth warning in the first run (the USBLC6-2's 5.25 V stand-off voltage
against a 5.5 V VBUS maximum) was a false positive in practice, and the rule now allows a TVS that margin.

I have not checked any of this on hardware. Findings 1 to 3 depend on currents that are sums of
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

Since the board has no known bugs, 25 were injected one at a time
(`python3 tools/fault_report.py <dino-board>`): each is one edit to the loaded design, and the test
requires a *new* error or warning from the check that should own it.

**25 of 25 are flagged.** On the first run it was 20 of 22: an address clash on a newly added part
and a too-low logic divider were missed, and a crossed I2C device and a P-FET with no gate
pull-down were caught only by unrelated findings. All four led to fixes in the checks. This is a test of the checks against mistakes I chose, on the
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
| **Historical:** status dividers 100k/100k, as first drawn | `power.logic_level` |
| **Historical:** regulator capacitors 1 uF 0402, as first drawn | `decoupling.regulator_caps` |

The last two are mistakes this board really had. Its `NOTES.md` records them as found by a design
review and fixed before the first commit; putting the old values back makes boardlint report both.

## What it did not look at

The board's notes list open items the tool has no check for: unrouted connections (DRC's job),
the antenna keep-out, footprint pin-1 and polarity against the assembler's library, connector
polarity of the LiPo lead, LED rail inrush, and the deep-discharge recovery problem its review
found. The last two are the kind of thing a part-model plus simulation approach could reach;
the others need footprint and mechanical data.
