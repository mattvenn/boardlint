# boardlint review: basic-ecp5-pcb

**2 errors, 7 warnings, 9 notes.** 80 components, 107 nets; netlist from the board.

- KiCad 5 legacy schematic: pin names read from the cache library, nets taken from the board (the legacy schematic itself is not netlisted)
- duplicate reference G*** on the board

## Errors

### U1.N10(CFG_0): 10k strap against the internal pull-up reads 1.08 V; a logic low must be below 0.8 V

`pin.strap_strength` · parts: U1, RN1.1 · nets: /fpga/cfg_0 · confidence: medium

U1 (ECP5U_45_CABGA256): RN1.1 (10k) pulls the pin down against an internal pull-up that can be as strong as 22k at 3.465 V. Use a much smaller resistor (1k or less) or tie the pin directly.

| | |
|---|---|
| external | 10k |
| internal_min | 22k |
| pin_voltage | 1.08 |
| threshold | 0.8 |

Basis: part model parts/ecp5.yaml (NOT verified against datasheet): weak pull current.

### U1.R10(CFG_2): 10k strap against the internal pull-up reads 1.08 V; a logic low must be below 0.8 V

`pin.strap_strength` · parts: U1, RN1.3 · nets: /fpga/cfg_2 · confidence: medium

U1 (ECP5U_45_CABGA256): RN1.3 (10k) pulls the pin down against an internal pull-up that can be as strong as 22k at 3.465 V. Use a much smaller resistor (1k or less) or tie the pin directly.

| | |
|---|---|
| external | 10k |
| internal_min | 22k |
| pin_voltage | 1.08 |
| threshold | 0.8 |

Basis: part model parts/ecp5.yaml (NOT verified against datasheet): weak pull current.

## Warnings

### U1 supply +1V1: nearest 100nF+ capacitor is 8.3 mm away

`decoupling.per_part` · parts: U1, C8 · nets: +1V1 · confidence: high

U1 (ECP5U_45_CABGA256) wants 1 within 6 mm of its supply pin; closest are C8 at 8.3 mm, C11 at 9.1 mm, C9 at 10.4 mm (pad to pad, straight line). Distance adds loop inductance: about 1 nH per mm of trace.

| | |
|---|---|
| required_mm | 6.0 |
| nearest_mm | 8.3 |

Basis: part model parts/ecp5.yaml (NOT verified against datasheet): core supply: 100 nF per pin group plus bulk; distance measured on the board.

### U1 supply +2V5: nearest 100nF+ capacitor is 11.8 mm away

`decoupling.per_part` · parts: U1, C22 · nets: +2V5 · confidence: high

U1 (ECP5U_45_CABGA256) wants 1 within 6 mm of its supply pin; closest are C22 at 11.8 mm, C26 at 12.1 mm, C20 at 37.7 mm (pad to pad, straight line). Distance adds loop inductance: about 1 nH per mm of trace.

| | |
|---|---|
| required_mm | 6.0 |
| nearest_mm | 11.82 |

Basis: part model parts/ecp5.yaml (NOT verified against datasheet); distance measured on the board.

### U1 supply +3.3VP: nearest 100nF+ capacitor is 6.9 mm away

`decoupling.per_part` · parts: U1, C6 · nets: +3.3VP · confidence: high

U1 (ECP5U_45_CABGA256) wants 1 within 6 mm of its supply pin; closest are C6 at 6.9 mm, C7 at 8.3 mm, C4 at 9.9 mm (pad to pad, straight line). Distance adds loop inductance: about 1 nH per mm of trace.

| | |
|---|---|
| required_mm | 6.0 |
| nearest_mm | 6.87 |

Basis: part model parts/ecp5.yaml (NOT verified against datasheet): 100 nF per VCCIO pin; distance measured on the board.

### X1: footprint pad(s) 2 have no pin on the symbol

`footprint.pin_map` · parts: X1 · confidence: medium

X1 (SiT2001B), symbol clock:SiT2001B, footprint Package_TO_SOT_SMD:SOT-23-5. They are unconnected on the board. Fine for mounting tabs; a mistake if the part has a function there (exposed pad, second row).

Basis: pin numbers in the schematic symbol against pad numbers in the board file.

### sd_clk is electrically long: 73 mm end to end, 444 ps one way

`layout.impedance` · parts: U1 · nets: sd_clk · confidence: low

SPI. 73 mm between its furthest pads (77 mm routed in all). For a 2 ns edge a trace acts as a transmission line beyond about 55 mm (delay over one sixth of the rise time). Nothing terminates it: expect overshoot and ringing at the far end. On a clock that can be seen as a second edge. A 22 to 47 ohm resistor at the driver is the usual fix. Line impedance about 72 ohm.

| | |
|---|---|
| end_to_end_mm | 72.8 |
| routed_mm | 77.3 |
| delay_ps | 444 |
| z0 | 72 |
| assumed_rise_ns | 2.0 |
| stack_up | assumed |

Basis: microstrip / stripline formulas on the stack-up; rise time is an assumption (signals: rise_ns in boardlint.yaml).

### U1.N9(CCLK/MCLK/SCK) cannot be used as an input, and J9.23(Pin_23), J2.23(Pin_23) can drive it

`mcu.pin_use` · parts: U1, J2, J9 · nets: sd_clk · confidence: medium

U1 (ECP5U_45_CABGA256): Configuration clock. In master-SPI mode the FPGA drives it; after configuration user logic can only drive it, through the USRMCLK primitive. It cannot be used as an input to the design. Net sd_clk also reaches J9.23(Pin_23), J2.23(Pin_23): a signal arriving from there cannot be seen by the design. If an external controller is meant to talk to logic in this part over these wires, bring its clock to an ordinary I/O pin as well.

Basis: part model parts/ecp5.yaml (NOT verified against datasheet).

### 2 supply net(s) have no known voltage

`power.rails` · nets: Net-(L2-Pad1), Net-(L3-Pad1) · confidence: high

Net-(L2-Pad1), Net-(L3-Pad1): voltage-dependent checks skip them. Declare them under rails: in boardlint.yaml.

## Notes

### Clock: X1 (SiT2001B) -> U1.A7(PT38A/+/PCLKT0_0) (clock-capable pin)

`clock.source` · parts: X1, U1 · nets: clk · confidence: medium

No series resistor: 22 to 33 ohm at the source tames edges on a long trace. 

### Line parameters of 2 fast net(s)

`layout.impedance` · confidence: low

sd_clk: 77 mm, 0.15 mm on F.Cu, 72 ohm, 471 ps, 6.0 pF, 88% over a plane, 3 vias; clk: 19 mm, 0.15 mm on F.Cu, 72 ohm, 114 ps, 1.6 pF, 100% over a plane, 0 vias.

| | |
|---|---|
| stack_up | assumed: F.Cu / 0.2 mm er 4.5, In1.Cu / 1.06 mm er 4.5, In2.Cu / 0.2 mm er 4.5 / B.Cu |

Basis: microstrip / stripline formulas on the stack-up.

### U1 pin use: 75 pins in use (61 plain connector I/O not listed)

`mcu.pin_use` · parts: U1 · confidence: medium

PT38A/+/PCLKT0_0 = clk: digital in (from X1.5(OUT)) [ok]; PB9B/-/D2/IO2 = sd_io2: digital in (from U2.3(IO2)) [ok]; PB9A/+/D3/IO3 = sd_io3: digital in (from U2.7(IO3)) [ok]; PB15A/+/HOLDN/DI/BUSY/CSSPIN/CEN = sd_cs: SPI chip select (U2) [ok]; CCLK/MCLK/SCK = sd_clk: SPI clock (U2) [cannot be read by the design]; PL59C/+/LDQ65 = button1: button [ok]; PL62B/-/HS/LDQ65 = led1: digital out (to D4.1(K)) [ok]; PL59D/-/LDQ65 = button2: button [ok]; PL62D/-/LDQ65 = led2: digital out (to D5.1(K)) [ok]; PB11A/+/D1/MISO/IO1 = sdi: digital in (from U2.2(DO(IO1))) [ok]; PB11B/-/D0/MOSI/IO0 = sdo: digital in (from U2.5(DI(IO0))) [ok]; CFG_0 = /fpga/cfg_0: to RN1.1.1 [ok; strapping pin]; CFG_1 = /fpga/cfg_1: to RN1.2.2 [ok; strapping pin]; CFG_2 = /fpga/cfg_2: to RN1.3.3 [ok; strapping pin]

| | |
|---|---|
| PT38A/+/PCLKT0_0 | clk: digital in (from X1.5(OUT)) [ok] |
| PB9B/-/D2/IO2 | sd_io2: digital in (from U2.3(IO2)) [ok] |
| PB9A/+/D3/IO3 | sd_io3: digital in (from U2.7(IO3)) [ok] |
| PB15A/+/HOLDN/DI/BUSY/CSSPIN/CEN | sd_cs: SPI chip select (U2) [ok] |
| CCLK/MCLK/SCK | sd_clk: SPI clock (U2) [cannot be read by the design] |
| PL59C/+/LDQ65 | button1: button [ok] |
| PL62B/-/HS/LDQ65 | led1: digital out (to D4.1(K)) [ok] |
| PL59D/-/LDQ65 | button2: button [ok] |
| PL62D/-/LDQ65 | led2: digital out (to D5.1(K)) [ok] |
| PB11A/+/D1/MISO/IO1 | sdi: digital in (from U2.2(DO(IO1))) [ok] |
| PB11B/-/D0/MOSI/IO0 | sdo: digital in (from U2.5(DI(IO0))) [ok] |
| CFG_0 | /fpga/cfg_0: to RN1.1.1 [ok; strapping pin] |
| CFG_1 | /fpga/cfg_1: to RN1.2.2 [ok; strapping pin] |
| CFG_2 | /fpga/cfg_2: to RN1.3.3 [ok; strapping pin] |

Basis: part model parts/ecp5.yaml (NOT verified against datasheet): pin capabilities; use inferred from what else is on each net.

### Strapping pin U1.N10(CFG_0) is used (/fpga/cfg_0)

`mcu.strapping` · parts: U1, RN1.1 · nets: /fpga/cfg_0 · confidence: medium

U1 (ECP5U_45_CABGA256) samples this pin at reset (note: CFG[2:0] = 010 selects master SPI (boot from flash); 001 slave SPI). Connected here: RN1.1.1. Whatever is attached must not hold the wrong level while the module comes out of reset.

Basis: part model parts/ecp5.yaml (NOT verified against datasheet).

### Strapping pin U1.P10(CFG_1) is used (/fpga/cfg_1)

`mcu.strapping` · parts: U1, RN1.2 · nets: /fpga/cfg_1 · confidence: medium

U1 (ECP5U_45_CABGA256) samples this pin at reset (note: CFG[2:0] = 010 selects master SPI (boot from flash); 001 slave SPI). Connected here: RN1.2.2. Whatever is attached must not hold the wrong level while the module comes out of reset.

Basis: part model parts/ecp5.yaml (NOT verified against datasheet).

### Strapping pin U1.R10(CFG_2) is used (/fpga/cfg_2)

`mcu.strapping` · parts: U1, RN1.3 · nets: /fpga/cfg_2 · confidence: medium

U1 (ECP5U_45_CABGA256) samples this pin at reset (note: CFG[2:0] = 010 selects master SPI (boot from flash); 001 slave SPI). Connected here: RN1.3.3. Whatever is attached must not hold the wrong level while the module comes out of reset.

Basis: part model parts/ecp5.yaml (NOT verified against datasheet).

### 7 supply rail(s) with a known voltage

`power.rails` · nets: +1V1, +2V5, +3.3VP, +5V, Net-(C12-Pad1), Net-(C13-Pad1) · confidence: medium

+1V1 1.045-1.155 V (net name); +2V5 2.375-2.625 V (net name); +3.3VP 3.135-3.465 V (net name); +5V 4.75-5.25 V (net name); Net-(C12-Pad1) 4.75-5.25 V (+5V through FB1); Net-(C13-Pad1) 4.75-5.25 V (+5V through FB2); Net-(C3-Pad1) 4.75-5.25 V (+5V through FB3)

Basis: regulator models, net names, boardlint.yaml; override with rails: in boardlint.yaml.

### 19 capacitor(s) on known rails carry no voltage rating in the schematic

`ratings.passives` · confidence: high

Add a Voltage property (or put it in the value, e.g. '10uF 16V') and they will be checked.

### Reset of U1: U1.R9(PROGRAMN) on creset

`reset.circuit` · parts: U1 · nets: creset · confidence: high

pull-up 10k (RN1.4); connector J9.13(Pin_13), J2.13(Pin_13), J10.10(Pin_10).

| | |
|---|---|
| pull_up | 10k |
| capacitance | none |
| tau_ms | None |

## Coverage

| Check | Status | |
|---|---|---|
| `clock.source` | ran | 1 finding(s), 0.00 s |
| `decoupling.per_part` | ran | 3 finding(s), 0.00 s |
| `decoupling.regulator_caps` | ran | 0 finding(s), 0.00 s |
| `footprint.pin_map` | ran | 1 finding(s), 0.00 s |
| `i2c.bus` | ran | 0 finding(s), 0.00 s |
| `layout.coupling` | ran | 0 finding(s), 0.03 s |
| `layout.impedance` | ran | 2 finding(s), 0.05 s |
| `layout.ir_drop` | ran | 0 finding(s), 0.00 s |
| `layout.return_path` | ran | 0 finding(s), 0.15 s |
| `layout.track_current` | ran | 0 finding(s), 0.00 s |
| `led.chain` | ran | 0 finding(s), 0.00 s |
| `load.inductive` | ran | 0 finding(s), 0.00 s |
| `mcu.alt_function` | ran | 0 finding(s), 0.00 s |
| `mcu.pin_use` | ran | 2 finding(s), 0.00 s |
| `mcu.strapping` | ran | 3 finding(s), 0.01 s |
| `net.name_mismatch` | ran | 0 finding(s), 0.00 s |
| `pin.floating_control` | ran | 0 finding(s), 0.00 s |
| `pin.name_voltage` | ran | 0 finding(s), 0.00 s |
| `pin.requirements` | ran | 0 finding(s), 0.00 s |
| `pin.strap_strength` | ran | 2 finding(s), 0.00 s |
| `polarity.polarised_parts` | ran | 0 finding(s), 0.00 s |
| `power.budget` | ran | 0 finding(s), 0.00 s |
| `power.droop` | ran | 0 finding(s), 0.00 s |
| `power.logic_level` | ran | 0 finding(s), 0.00 s |
| `power.pin_voltage` | ran | 0 finding(s), 0.30 s |
| `power.rails` | ran | 2 finding(s), 0.00 s |
| `power.regulator` | ran | 0 finding(s), 0.00 s |
| `power.source_pin` | ran | 0 finding(s), 0.00 s |
| `power.supply_range` | ran | 0 finding(s), 0.00 s |
| `ratings.fets` | ran | 0 finding(s), 0.00 s |
| `ratings.passives` | ran | 1 finding(s), 0.00 s |
| `reset.circuit` | ran | 1 finding(s), 0.00 s |
| `sim.i2c` | ran | 0 finding(s), 0.00 s |
| `sim.led_chain` | ran | 0 finding(s), 0.00 s |
| `spi.bus` | ran | 0 finding(s), 0.00 s |
| `sync.schematic_board` | ran | 0 finding(s), 0.00 s |
| `uart.direction` | ran | 0 finding(s), 0.00 s |
| `usb.wiring` | ran | 0 finding(s), 0.00 s |

## Part models

| Parts | Value | Model | Verified against datasheet |
|---|---|---|---|
| D1, D3, D4, D5 | LED | **none: heuristics only** |  |
| J1 | Conn_01x02 | **none: heuristics only** |  |
| J10 | Conn_02x05_Odd_Even | **none: heuristics only** |  |
| J2, J9 | Conn_02x20_Odd_Even | **none: heuristics only** |  |
| J3, J4, J5, J6 +2 | Conn_02x06_Odd_Even | **none: heuristics only** |  |
| Q1 | Q_NMOS_GSD | **none: heuristics only** |  |
| SW1, SW2 | SW_Push | **none: heuristics only** |  |
| U1 | ECP5U_45_CABGA256 | ecp5 | no |
| U2 | W25Q128JVSIM | **none: heuristics only** |  |
| U3, U4 | TLV62568DBV | **none: heuristics only** |  |
| U5 | TLV73325PDBV | **none: heuristics only** |  |

## Known issues of the parts used

From errata sheets and forums, recorded in the part models. Not checked against this design.

- **ECP5U_45_CABGA256** (cclk-not-a-user-input): The configuration clock pin (CCLK/MCLK) cannot be read by user logic. A board that shares the flash SPI bus with an external controller cannot receive that controller's clock on this pin: route the clock to an ordinary I/O as well. Source: https://github.com/mattvenn/basic-ecp5-pcb/issues/3
