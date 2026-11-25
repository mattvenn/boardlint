# Test run: basic-ecp5-pcb

This review was produced by Claude (Anthropic's AI model). Nothing here has been checked on hardware.

Board: <https://github.com/mattvenn/basic-ecp5-pcb> at `f5ee05d` (2020-12-05). An ECP5 FPGA dev
board: LFE5U in CABGA256, W25Q128 configuration flash shared with a Raspberry Pi header, a 16 MHz
SiT2001 oscillator, two buck converters and an LDO, six PMODs. KiCad 5, four layers.

This board was built, and its README has an errata list. That makes it a blind test with a known
answer: the errata were not used to write the checks, only to choose which checks to write.

Full output: [examples/basic-ecp5-pcb-report.md](examples/basic-ecp5-pcb-report.md).

```
basic-ecp5-pcb: 2 errors, 6 warnings, 9 notes
```

## The README's errata against the report

| Erratum (from the README) | Found? | Finding |
|---|---|---|
| "configuration bits for FPGA should be tied to gnd not through a 10k resistor. The voltage is about 1v" | **yes** | `pin.strap_strength` (error, twice): CFG_0 and CFG_2, 10k against an internal pull-up as strong as 22k, read 1.08 V; a low must be under 0.8 V |
| "ecp5 SPI clock pin can't be used as an input, so have to add a bodge wire for SPI peripheral comms with Pi" | **yes** | `mcu.pin_use` (warning): `CCLK/MCLK/SCK` cannot be read by the design, and the Pi header's pins 23 can drive it |
| "used IS25LP016D-JBLE as flash, but it has problems with enabling QE for QSPI" | no | A property of one flash part's firmware interface. It belongs in that part's model as an erratum; there is no model for it, and the schematic now shows the replacement part |
| "Add missing qspi to the Pi to be able to program bitstream faster" | no | A missing feature, not a wrong connection. Nothing in the design says the Pi was meant to reach IO2 and IO3 |

Two of four, and they are the two that are wiring mistakes.

The computed 1.08 V matches the README's "about 1v". It comes from the weak pull-up current Claude
recalled for ECP5 configuration pins (up to 150 µA); the model is marked unverified, so read the
agreement as encouraging, not as proof.

## Other things it reported

- **Clock:** the oscillator output arrives at `PT38A/PCLKT0_0`, a primary-clock pin. That is the
  README's own requirement ("Has to go to a PCLK pad"), confirmed. A test moves the clock to an
  ordinary I/O and requires an error.
- **Reset:** PROGRAMN has a 10k pull-up and is reachable from the Pi header and the JTAG header.
- **Decoupling:** nearest 100 nF is 7 to 12 mm (pad to pad) from the closest supply ball on each of
  the three rails. On a four-layer board with planes this matters less than the number suggests;
  the check does not yet know about planes.
- **Not checked:** the two TLV62568 bucks (no models: feedback dividers, inductor ratings and
  output voltage are not looked at), and nothing was simulated (no modelled regulators or buses).

## What it took to read this board

- KiCad 5 legacy schematics are not netlisted. Pin names and types are read from the project's
  `-cache.lib`; nets come from the `.kicad_pcb`. So a KiCad 5 project is checkable once it has a board.
- A new part model, `ecp5.yaml`: configuration pins with their internal pulls, the CCLK
  restriction, a pattern for clock-capable pins (`PCLK`, `GR_PCLK`), and the three supply domains.
  Written from memory and marked unverified.
- Resistor networks are now split into individual resistors, so a strap through one element of a
  pack is seen like any other strap.
- I/O pins of a part with several supply domains are judged against its highest rail. Before
  that, every 3.3 V signal into the FPGA was reported as exceeding the 2.5 V auxiliary supply.

## Update, 2026-11-25: copper extraction

The linked report was regenerated with the copper extraction
([copper-extraction.md](copper-extraction.md)): 2 errors, 7 warnings, 9 notes. One new warning:
`layout.impedance` finds the SD card clock `sd_clk` 72 mm end to end with no series resistor
(assumed 2 ns edge, low confidence). The supply rails are not solved on this board: its regulators have no model, and
the FPGA model gives no supply current.
