# Test run: Density MIDI controller

This review was produced by Claude (Anthropic's AI model). Nothing here has been checked on hardware.

Board: <https://github.com/mo-seph/density> at `9a126c2` (2026-11-24), `proto-125x130`, prototype
v0.1 as ordered. A MIDI controller: 16 potentiometers and a fader read through a CD74HC4067
multiplexer, an MCP6002 buffer and an MCP3208 analogue-to-digital converter (ADC); 20 buttons on
three 74HC165 shift registers; 20 SK6812 addressable LEDs behind a 74AHCT1G125 level shifter; a
plug-in Waveshare RP2350-Zero. KiCad, four layers, 186 parts.

Full output: [examples/density-report.md](examples/density-report.md).

```
density_proto: 0 errors, 2 warnings, 16 notes
schematic and board netlists agree (104 multi-pin nets)
```

## What it found

| Finding | In the board's notes? |
|---|---|
| `power.source_pin`: the 20 LEDs can draw 811 mA from the module's 5V pad, which is the USB port's VBUS with no diode or fuse | Yes: the notes give 0.72 to 0.81 A and ask for a firmware cap of about 350 to 400 mA |
| `decoupling.per_part`: the nearest bypass capacitor to the op-amp U4 is 4.4 mm from its supply pin; the MCP6002 datasheet asks for 2 mm | Partly: the notes accept 7 to 11 mm for the ADC and the shift registers and say why, but do not mention U4 |

One thing that is not in the notes, from the RP2350 datasheet (recorded in the module's model as an
erratum): with the hardware SPI chip-select function in SPI mode 0, chip select pulses high between
data words. The MCP3208 needs chip select held low across its whole frame. Firmware should use
mode 3, or drive GP5 as a plain output.

Checked and passing:

- SPI is on pins that have those functions on the RP2350 (GP2 clock, GP3 transmit, GP4 receive,
  GP5 chip select), and I2C is on GP14 and GP15.
- The LED chain is D1 to D20 in order, driven by the level shifter through 33 Ω, and the first
  LED's logic level is met (3.99 V against a 2.6 V threshold). In simulation all 20 latch data.
- The I2C lines have 4.7 kΩ pull-ups. With a cable and a module attached, the estimated rise time
  (340 ns) is over the 300 ns limit of 400 kHz mode; at 100 kHz it is fine.

## What it did not look at

- The shift-register chain (each register's serial output into the next one's serial input).
  There is no chain check for shift registers yet; the addressable-LED one does not cover them.
- The pedal inputs: unbuffered into the ADC through 1 kΩ, with no clamp. The notes say to use
  expression pedals only.
- The 44 µF across USB 5 V, which the notes already list. The USB connector is on the module, so
  boardlint's USB inrush check does not see it.
- The rotary encoder (no model).

## What it took

Seven part models, all read from datasheets: RP2350-Zero, MCP3208, MCP6002, CD74HC4067, 74HC165,
74AHCT1G125 and SK6812MINI-RV.

Checks that changed because of this board:

- SPI lines named for the ADC (`ADC_SCK`, `ADC_MISO`) are no longer classed as analogue nodes.
- I2C buses on freely assignable MCU pins are found from nets named SDA and SCL.
- `power.source_pin` is new, and treats a module's USB VBUS pad as a 500 mA source.

## Update, 2026-11-25: copper extraction

The linked report was regenerated with the copper extraction
([copper-extraction.md](copper-extraction.md)): 0 errors, 5 warnings, 18 notes. The three new
warnings have not been checked against the board's notes by its designer:

- `layout.track_current`: a 0.5 mm segment of +5V on an inner layer carries all 811 mA of the LED
  supply, for 27 mm; IPC-2221 gives 438 mA there for a 10 °C rise in 0.5 oz (17.5 µm) inner copper,
  which is the default assumed when the board file has no stack-up. It depends on the same worst-case LED
  current as the `power.source_pin` finding, so the firmware cap the notes ask for clears both.
- `layout.impedance` x2: the shift-register clock `SR_CLK` (106 mm end to end) and the ADC clock
  `ADC_SCK` (58 mm) have no series resistor. With an assumed 2 ns edge, anything over about 55 mm
  can ring. Low confidence: the real edge rate of the RP2350 pin at its default drive is not modelled.

A note: 136 mV (2.7 %) is lost on +5V on the way to the furthest LED.

The extraction behind these figures was checked against an independent solver: [crosscheck.md](crosscheck.md).
