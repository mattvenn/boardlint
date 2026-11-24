# Test run: ezbldc

This review was produced by Claude (Anthropic's AI model). Nothing here has been checked on hardware.

Board: <https://github.com/mo-seph/ezbldc> at `212d040` (2026-11-24), revision v0.4. A four-channel
driver for small brushless motors: a Seeed XIAO ESP32-S3 Plus, four TI DRV8313 three-phase
drivers, a 74HC139 decoder for four encoder ports, a 7805 regulator, and I2C on two Qwiic
connectors. KiCad 10, four layers, 100 parts. Its README says the design is unproven on hardware.

Full output: [examples/ezbldc-report.md](examples/ezbldc-report.md).

```
bldc_driver_board: 0 errors, 3 warnings, 11 notes
schematic and board netlists agree (76 multi-pin nets)
```

## What it found

Both warnings are already stated in the board's README.

| Finding | In the README? |
|---|---|
| `i2c.bus` (two warnings): no pull-ups on SDA and SCL, which leave the board on the Qwiic connectors | Yes: "Pull-ups are not fitted" |
| `power.supply_range`: the status LED runs from 3.3 V; its minimum is 3.5 V | Yes, under "Things to know" |

Notes worth reading:

- **7805 temperature.** About 72 °C at typical load (84 mA, 639 mW, 50 °C/W, 40 °C ambient). At the
  Wi-Fi peak of 358 mA it would be 2.7 W and over 125 °C if that lasted. The README says the same:
  it wants a heatsink with Wi-Fi on.
- **Status LED data line.** The fitted part (LCSC C2843785) is a XINGLIGHT clone of the WS2812B.
  Its datasheet asks for a series resistor on DIN; LED_DATA has none.
- **GPIO43** (encoder select A0) is the ESP32-S3's UART0 transmit pin and carries the boot log at
  reset, so the encoder select toggles briefly at power-up.
- **GPIO3** (motor 3 IN2) is a strapping pin. It is ignored with default eFuses.
- **XIAO 3V3 pin:** about 36 mA of its 700 mA is accounted for.

Checked and passing: on all four DRV8313 channels the charge-pump capacitor (10 nF between CPH and
CPL), the VCP capacitor (100 nF to VM), the V3P3 capacitor (470 nF) and the VM capacitors (100 µF
and two 100 nF) are present with the datasheet values. The driver reset line has a 10 kΩ
pull-down, so the outputs are off until the microcontroller raises it.

## What it did not look at

- Motor phase current against trace width, the 1.1 A polyfuses and the DRV8313's ratings. Motor
  currents are not in any model: they depend on what is plugged in.
- The shared encoder bus. The README's own concern (an MT6701 with its chip select high may not
  release the data line) is about a part that is not on the board.
- The reverse-polarity diode's dissipation and the TVS clamp against the supply.
- Whether each fault LED's current is within the DRV8313's nFAULT sink rating.

## What it took

Nine part models, all read from datasheets: DRV8313, XIAO ESP32-S3 Plus, 74HC139, L7805, the
Worldsemi WS2812B and the XINGLIGHT clone actually fitted, SS14, SS54 and SMAJ15A. The plain fault
LEDs have no model.

Checks that changed because of this board:

- A fault output that sinks an indicator LED is no longer reported as an open-drain pin with no pull-up.
- Rail voltages are taken from a part's own supply-output pin (the DRV8313's V3P3, the XIAO's 3V3).
- A capacitor required between two pins of one part (`cap_to_pin`) can be stated and checked.
- Regulator temperature is judged on typical load, with the sustained-peak figure given as a note.
- A supply plane on the next layer counts as a reference for `layout.return_path`. Before that, the
  encoder clock was reported as having no ground beneath it while running over the 3.3 V plane.
