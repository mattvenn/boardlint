# Regression corpus: real bugs with a fix commit

Public KiCad 6+ projects where one commit fixes a real hardware mistake. For each,
`tools/regress.py` checks out the parent (buggy) and the fix, runs boardlint on both, and reports
the errors and warnings that exist only before the fix. The list is `tests/corpus.yaml`. Nothing
from these repositories is vendored.

```bash
python3 tools/regress.py /tmp/boardlint-regress
```

## Results (2026-11-23)

| Project | Bug | Result | Flagged by |
|---|---|---|---|
| [corybuecker/reflow-oven](https://github.com/corybuecker/reflow-oven) `2777bea` → `f98bfb7` | USB-C receptacle with no CC pull-downs | caught, first run | `usb.wiring`: CC1 and CC2 not connected |
| [corygrant/USB2CAN_HW](https://github.com/corygrant/USB2CAN_HW) `b687a59` → `7dda525` | USB-C receptacle with no CC resistors | caught, first run | `usb.wiring` |
| [Galacs/valrob-carte-ihm-cdf-1](https://github.com/Galacs/valrob-carte-ihm-cdf-1) `971a2a4` → `a2ce01f` | I2C bus with no pull-ups | caught, first run | `i2c.bus`: no pull-up on SDA, SCL |
| [system76/launch](https://github.com/system76/launch) `73b64f9` → `9261cb4` | SDA and SCL swapped at the RP2040 | caught after adding a check | `mcu.alt_function`: GPIO26 can only be SDA, GPIO27 only SCL |
| [nelgau/hicart](https://github.com/nelgau/hicart) `6e3008c` → `de2819e` | USB D+ and D- crossed at the ESD part | caught after adding a rule | `usb.wiring`: D+ and D- joined through the USBLC6-2's paired pins |
| [OpenRTX/RC-1](https://github.com/OpenRTX/RC-1) `7b5165d` → `d9c0fbd` | Review commit: VDDCORE tied to 3V3, 3.3 V reset into a 1.8 V M.2 pin, missing decouplers | partly caught after adding a check | `pin.name_voltage`: the first two. The missing decouplers are not flagged (no ATSAMD51 model) |
| [SeraphimlabsLLC/Crystal](https://github.com/SeraphimlabsLLC/Crystal) `d6c00a3` → `e8c4f88` | UART TX/RX swapped at a 4-pin header | not detectable | The header pins are unnamed (`Pin_2`, `Pin_3`). Which is TX is a property of the mating cable |
| [chipsalliance/rocket-pcb](https://github.com/chipsalliance/rocket-pcb) `5f3d34f` → `e67bb53` | "swap D+ and D- of the ESD protection pin" | not detectable | The commit moves D+ and D- to the other channel pair of a four-channel TVS array. Both versions are electrically valid |

**First run, before any change: 3 of 8.** After reading why each miss was missed, three checks were
added or extended and the count is **6 of 8**, with the remaining two outside what design files can show.

The 6 of 8 is not a detection rate. The checks were changed after seeing these cases, so it only
shows that the mechanisms now exist. An honest rate needs a second set of bugs the tool has not
been tuned on. The first-run 3 of 8 is the closest thing here to an unbiased number, and it is a
small sample.

## What the misses taught

- **Fixed-function MCU pins matter.** `i2c.bus` could not see the launch bug because an RP2040
  GPIO has no "SDA" in its name. The fix was a per-pin `alt:` list in the MCU's model and a check
  that compares it with what the net is used for. Every MCU family needs this table; STM32 and
  others can be generated from open pin databases.
- **Some parts are wires.** A flow-through ESD array has pin pairs that are one node. Treating
  those pairs as connectivity (`internal_links` in the model) let the existing D+/D- rule see the short.
- **Pin names carry voltages.** `RESET#_(O)_(0/1.8V)` and `VDDCORE` say enough to flag a 3.3 V
  net without any model. Low confidence, and cheap.
- **The schematic reader had two bugs that one board could not show.** A mirrored symbol rotated
  by 90 or 270 degrees had its pins exchanged (rotation is applied before the mirror, not after),
  and coordinates ending in 5 um were rounded apart. Both hid on the reference board and showed up
  as schematic-versus-board differences here. After the fixes the built-in netlister agrees with
  the board exactly on six of the seven projects that have both files. The seventh (launch) differs
  in 3 of 351 net groups, where two ground nets are one on the board; I did not find out why.
  rocket-pcb uses schematic buses, which are not expanded.
- **Unannotated schematics are real input.** RC-1's parts were all `U?`, `C?`. The loader merged
  them; it now keeps them apart.
- **The board file can be stale.** rocket-pcb's fix touched only the schematic. boardlint used the
  board's netlist by default and saw no change. It warns when the two netlists differ; the corpus
  entry forces `--netlist-from sch`.
- **Connector pinouts are outside the design.** A swapped TX/RX at an unlabelled header cannot be
  judged without knowing the cable. A library of standard header pinouts (FTDI 6-pin, SWD, Qwiic,
  Pmod) would cover the common cases.

## False positives seen on these boards

Running on sixteen revisions of eight unfamiliar projects also showed where the tool was wrong.
All of these were fixed the same day:

| Seen | Cause | Change |
|---|---|---|
| 77 "decoupling capacitor far away" warnings on a 100-key keyboard | one warning per LED | identical findings on four or more parts are merged into one |
| "5 V into a 3.3 V pin" on a level shifter's low-voltage side, and on an FPGA's 1.8 V bank | a part with several supply rails and no model: the tool guessed the highest rail | level inference is skipped for multi-rail parts without a model |
| "no controller on the I2C bus" | MCU without a model: its pins had no role | a general-purpose pin of an unmodelled IC counts as a possible controller |
| "no pull-up" as an error on an FMC mezzanine's I2C | the controller and its pull-ups are on the carrier | warning, with that explanation, when the bus leaves through a connector and no controller is on the board |
| "SPI clock not driven" on a USB hub's unused multi-function pins | pin-name guess on a pin with three functions | skipped for multi-function pins of unmodelled parts |
| "reset pin floats" on an STM32 | internal pull-up; no model to say so | note, not warning, for reset pins of unmodelled parts |
| TVS stand-off voltage 5.25 V against VBUS up to 5.5 V | pedantic | a TVS is allowed 6 % over its stand-off voltage |

The pattern: almost every false positive came from a part with no model. That is the case for
investing in the model library first.

Real findings on the fixed revisions that look worth the owners' attention, but which I have not
verified: a 3.3 V ESP32 driving 5 V-powered addressable LEDs directly (valrob), USB data lines
running 0.2 mm from analog inputs for 10 mm (Crystal), and an M.2 1.8 V GPIO on a 3.3 V net after
the RC-1 fix.

## More candidates, not yet in the corpus

Found by the same search, not verified to the same level:

- `NemoAndrea/freezer-display` `c570176`: MISO/MOSI labels swapped (naming only; the board worked)
- `syic0o/led-cube4` `83ab70a`: reset pull-up added
- `JuliCai/PCRuler` `5b327d6`: CC resistors added (large mixed commit)
- `coderkalyan/picofusion_h20` `b42ba5b`: GNSS UART swap, bundled with a KiCad 7 migration
- `davidday99/6502-sbc` `3cf47c3`: TX/RX and RTS/CTS swap plus a RAM pinout fix
- `Swyter/psdaptwor` `3eed20b`: MOSFET pins shorted
- `antsouchlos/commonsense-hw` `cb4059b`: I2C pull-ups added
- `InfraredAces/rp2040-brook` `bc5b138`: OLED SDA/SCL swap
- `smkent/pcb` `cb16f5b`: SK6812SIDE footprint pinout fix
- `hubertciebiada/open-ambient-sensor` `85d8a7a`: connector pin order reversed
- `skot/bitaxe` `0950fce`: CC pull-downs; `mdrobot7/pico-vga` `bd8d0df`: I2C pull-ups

No addressable-LED direction fix and no regulator-feedback fix was found in the time available.
