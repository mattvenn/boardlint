# boardlint review: density_proto

**0 errors, 5 warnings, 18 notes.** 186 components, 104 nets; netlist from the board.

- schematic and board netlists agree (104 multi-pin nets)

## Warnings

### U4 supply AVDD: nearest 10nF+ capacitor is 4.4 mm away

`decoupling.per_part` · parts: U4, C29 · nets: AVDD · confidence: high

U4 (MCP6002T-I/SN) wants 1 within 2 mm of its supply pin; closest are C29 at 4.4 mm, C28 at 6.0 mm, C27 at 7.7 mm (pad to pad, straight line). Distance adds loop inductance: about 1 nH per mm of trace.

| | |
|---|---|
| required_mm | 2.0 |
| nearest_mm | 4.38 |

Basis: part model parts/mcp6002.yaml (verified against datasheet): local bypass 0.01 uF to 0.1 uF within 2 mm of the VDD pin (section 4.4); distance measured on the board.

### ADC_SCK is electrically long: 58 mm end to end, 347 ps one way

`layout.impedance` · parts: A1 · nets: ADC_SCK · confidence: low

clock. 58 mm between its furthest pads (59 mm routed in all). For a 2 ns edge a trace acts as a transmission line beyond about 56 mm (delay over one sixth of the rise time). Nothing terminates it: expect overshoot and ringing at the far end. On a clock that can be seen as a second edge. A 22 to 47 ohm resistor at the driver is the usual fix. Line impedance about 72 ohm.

| | |
|---|---|
| end_to_end_mm | 57.7 |
| routed_mm | 58.8 |
| delay_ps | 347 |
| z0 | 72 |
| assumed_rise_ns | 2.0 |
| stack_up | assumed |

Basis: microstrip / stripline formulas on the stack-up; rise time is an assumption (signals: rise_ns in boardlint.yaml).

### SR_CLK is electrically long: 106 mm end to end, 650 ps one way

`layout.impedance` · parts: A1 · nets: SR_CLK · confidence: low

clock. 106 mm between its furthest pads (119 mm routed in all). For a 2 ns edge a trace acts as a transmission line beyond about 54 mm (delay over one sixth of the rise time). Nothing terminates it: expect overshoot and ringing at the far end. On a clock that can be seen as a second edge. A 22 to 47 ohm resistor at the driver is the usual fix. Line impedance about 82 ohm.

| | |
|---|---|
| end_to_end_mm | 106.0 |
| routed_mm | 119.0 |
| delay_ps | 650 |
| z0 | 82 |
| assumed_rise_ns | 2.0 |
| stack_up | assumed |

Basis: microstrip / stripline formulas on the stack-up; rise time is an assumption (signals: rise_ns in boardlint.yaml).

### +5V: a 0.5 mm segment carries 811 mA; IPC-2221 gives 438 mA for a 10 C rise

`layout.track_current` · nets: +5V · confidence: medium

At (95.5, 78.2) mm on In2.Cu, an inner layer. 26.9 mm of the net's track is over its limit with every load at maximum. This is the current that segment actually carries in the solved network, not the net's total.

| | |
|---|---|
| segment | (95.5, 78.2) mm on In2.Cu |
| width_mm | 0.5 |
| current_A | 0.811 |
| ipc2221_A | 0.44 |
| length_over_limit_mm | 26.9 |
| net_total_A | 0.811 |

Basis: IPC-2221 formula; segment current from the resistor-network solve; loads are model maxima.

### A1.1(5V) supplies +5V: up to 811 mA is drawn, and it is the USB port's VBUS (500 mA from a USB 2.0 port)

`power.source_pin` · parts: A1, U8, D1, D2, D3 · nets: +5V · confidence: medium

A1 (RP2350-Zero). Loads on +5V: D1 40.5 mA, D2 40.5 mA, D3 40.5 mA, D4 40.5 mA, D5 40.5 mA, +16 more. This is every load at its maximum at once. The module's own current comes on top. A USB-C charger or a port that advertises 1.5 A or 3 A gives more; a plain USB 2.0 port may shut down or droop. Limit the current in firmware or add a hardware limit.

| | |
|---|---|
| pin | A1.1(5V) |
| limit_mA | 500.0 |
| load_max_mA | 811.4 |
| loads | D1 40.5 mA, D2 40.5 mA, D3 40.5 mA, D4 40.5 mA, D5 40.5 mA, +16 more |
| not_counted | none |

Basis: part model parts/rp2350-zero.yaml (verified against datasheet).

## Notes

### I2C net SCL leaves the board with 4.7k already fitted

`i2c.bus` · nets: SCL · confidence: medium

Breakout modules usually carry their own pull-ups (2.2k to 10k each); every one plugged in lowers the total. Budget for the 3 mA limit.

| | |
|---|---|
| pullups | {'R10': '4.7k'} |
| effective | 4.7k |
| rail | +3V3 |
| r_min_3mA | 1.022k |
| bus_c_est_pF | 88 |
| t_rise_ns | 349 |

### I2C net SDA leaves the board with 4.7k already fitted

`i2c.bus` · nets: SDA · confidence: medium

Breakout modules usually carry their own pull-ups (2.2k to 10k each); every one plugged in lowers the total. Budget for the 3 mA limit.

| | |
|---|---|
| pullups | {'R11': '4.7k'} |
| effective | 4.7k |
| rail | +3V3 |
| r_min_3mA | 1.022k |
| bus_c_est_pF | 89 |
| t_rise_ns | 354 |

### I2C pull-up on SCL (4.7k) is too weak for 400 kHz once a cable and module are plugged in

`i2c.bus` · parts: R10 · nets: SCL · confidence: medium

Estimated rise time 349 ns with about 88 pF (board alone: 150 ns; 50 pF allowed for the connector): fine at 100 kHz (limit 1000 ns), over the 300 ns limit of fast mode.

| | |
|---|---|
| pullups | {'R10': '4.7k'} |
| effective | 4.7k |
| rail | +3V3 |
| r_min_3mA | 1.022k |
| bus_c_est_pF | 88 |
| t_rise_ns | 349 |

Basis: I2C specification (UM10204) table 11: tr; bus capacitance is an estimate.

### I2C pull-up on SDA (4.7k) is too weak for 400 kHz once a cable and module are plugged in

`i2c.bus` · parts: R11 · nets: SDA · confidence: medium

Estimated rise time 354 ns with about 89 pF (board alone: 155 ns; 50 pF allowed for the connector): fine at 100 kHz (limit 1000 ns), over the 300 ns limit of fast mode.

| | |
|---|---|
| pullups | {'R11': '4.7k'} |
| effective | 4.7k |
| rail | +3V3 |
| r_min_3mA | 1.022k |
| bus_c_est_pF | 89 |
| t_rise_ns | 354 |

Basis: I2C specification (UM10204) table 11: tr; bus capacitance is an estimate.

### LEDC14 couples into BUFA (analog / measurement node)

`layout.coupling` · nets: BUFA, LEDC14 · confidence: low

LEDC14 (addressable-LED data (800 kHz, nanosecond edges)) runs 1 mm side by side on one layer, down to 0.66 mm apart. Each aggressor edge kicks the victim by about 7 mV (capacitive divider against 5 pF on the node). Estimated 0.01 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.011 |
| side_by_side_mm | 0.9 |
| min_gap_mm | 0.66 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 0.4 |
| aggressor | LEDC14: addressable-LED data (800 kHz, nanosecond edges), 3.3 V swing |
| victim | BUFA: analog / measurement node |
| victim_node_C_pF | 5.0 |
| injected_step_est_mV | 7.0 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### Net classes used for coupling: 26 aggressor, 26 victim net(s)

`layout.coupling` · confidence: medium

Aggressors: ADC_MISO, ADC_MOSI, ADC_SCK, LEDC1, LEDC10, LEDC11, LEDC12, LEDC13, LEDC14, LEDC15, LEDC16, LEDC17, LEDC18, LEDC19.... Victims: ADC0, ADC1, BUFA, BUFB, FADER1, MUXA, PED1_TIP, PED2_TIP, PEDAL1, PEDAL2, POT1, POT10, POT11, POT12, POT13, POT14, POT15, POT16, POT2, POT3....

### ADC_MISO is electrically long: 60 mm end to end, 358 ps one way

`layout.impedance` · parts: A1, U3 · nets: ADC_MISO · confidence: low

SPI. 60 mm between its furthest pads (61 mm routed in all). For a 2 ns edge a trace acts as a transmission line beyond about 56 mm (delay over one sixth of the rise time). Nothing terminates it: expect overshoot and ringing at the far end. This is a data line sampled after it settles, so it matters less than on a clock. Line impedance about 72 ohm.

| | |
|---|---|
| end_to_end_mm | 59.6 |
| routed_mm | 61.3 |
| delay_ps | 358 |
| z0 | 72 |
| assumed_rise_ns | 2.0 |
| stack_up | assumed |

Basis: microstrip / stripline formulas on the stack-up; rise time is an assumption (signals: rise_ns in boardlint.yaml).

### Line parameters of 25 fast net(s)

`layout.impedance` · confidence: low

SR_CLK: 119 mm, 0.15 mm on B.Cu, 82 ohm, 730 ps, 9.1 pF, 97% over a plane, 4 vias; ADC_MISO: 61 mm, 0.15 mm on F.Cu, 72 ohm, 368 ps, 5.0 pF, 98% over a plane, 0 vias; ADC_SCK: 59 mm, 0.15 mm on F.Cu, 72 ohm, 353 ps, 4.8 pF, 98% over a plane, 0 vias; ADC_MOSI: 33 mm, 0.15 mm on F.Cu, 72 ohm, 203 ps, 2.7 pF, 95% over a plane, 2 vias; LEDC16: 33 mm, 0.15 mm on In2.Cu, 66 ohm, 230 ps, 3.3 pF, 94% over a plane, 2 vias; LEDC4: 27 mm, 0.15 mm on In2.Cu, 67 ohm, 186 ps, 2.8 pF, 99% over a plane, 2 vias; LEDC12: 27 mm, 0.15 mm on In2.Cu, 67 ohm, 186 ps, 2.8 pF, 99% over a plane, 2 vias; LEDC8: 26 mm, 0.15 mm on F.Cu, 72 ohm, 153 ps, 2.1 pF, 100% over a plane, 0 vias; LEDC10: 24 mm, 0.15 mm on In2.Cu, 93 ohm, 162 ps, 1.9 pF, 95% over a plane, 2 vias; LEDC7: 23 mm, 0.15 mm on In2.Cu, 68 ohm, 153 ps, 2.2 pF, 96% over a plane, 2 vias....

| | |
|---|---|
| stack_up | assumed: F.Cu / 0.2 mm er 4.5, In1.Cu / 1.095 mm er 4.5, In2.Cu / 0.2 mm er 4.5 / B.Cu |

Basis: microstrip / stripline formulas on the stack-up.

### +5V: 136 mV is lost in the copper on the way to D5.2(VDD) (2.7% of the rail)

`layout.ir_drop` · parts: D5, A1 · nets: +5V · confidence: medium

With every load on +5V at its maximum (811 mA in all), fed from A1 5V pin. Supply side 135 mV, ground return 0 mV. Solved on the routed copper: track resistance, via barrels and pours as a sheet-resistance mesh. Copper at 20 C; thermal-relief spokes are not modelled.

| | |
|---|---|
| source | A1 5V pin |
| total_load_A | 0.811 |
| worst | D5.2(VDD): 136 mV (135 supply + 0 return) |
| next | D4.2(VDD) 135 mV; D3.2(VDD) 132 mV; D6.2(VDD) 130 mV |
| copper | 290 track segments, 21 vias, 0 pour cells |
| ground | ground return through GND to A1.2(GND) included (19995 pour cells, grid 1.6 mm) |
| stack_up | assumed |

Basis: resistor-network solve of the net's copper (boardlint/extract.py); loads are model maxima.

### LEDC14: 26% of its 23 mm has no ground or supply plane on the next layer

`layout.return_path` · nets: LEDC14 · confidence: medium

LEDC14 (addressable-LED data (800 kHz, nanosecond edges)). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 9 stretch(es) without cover.

| | |
|---|---|
| length_mm | 22.7 |
| uncovered_mm | 5.8 |
| stretches | 9 |

Basis: filled ground and supply zones in the board file, sampled every 0.5 mm along the tracks.

### D1 DIN logic level is met

`led.chain` · parts: U8, D1 · nets: LED_5V, LED_DIN · confidence: high

Output high 3.99 V against a threshold of at most 2.60 V.

| | |
|---|---|
| driver_rail | +5V 4.75-5.25 V |
| driver_voh_min | 3.99 |
| led_rail | +5V 4.75-5.25 V |
| led_vih | 2.60-2.60 V |

Basis: part model parts/sk6812mini-rv.yaml (verified against datasheet): VIH.

### LED chain on LED_5V

`led.chain` · parts: D1, U8 · nets: LED_5V, LED_DIN · confidence: high

20 LED(s): D1, D2, ... D20; driven by U8.4 through R9 (33R).

### A1 pin use: 20 pins in use

`mcu.pin_use` · parts: A1 · confidence: medium

GP29 = GP29: to connector J5.8(Pin_8) [ok]; GP28 = GP28: to connector J5.7(Pin_7) [ok]; GP27 = GP27: to connector J5.6(Pin_6) [ok]; GP26 = GP26: to connector J5.5(Pin_5) [ok]; GP15 = SCL: to connector J1.3(Pin_3) [ok]; GP14 = SDA: to connector J1.4(Pin_4) [ok]; GP13 = LED_DATA: digital out (to U8.2) [ok]; GP12 = SR_DATA: digital in (from U5.9(Q7)) [ok]; GP11 = SR_LOAD: digital out (to U7.1(~{PL})) [ok]; GP10 = SR_CLK: digital out (to U7.2(CP)) [ok]; GP9 = MUX_S3: digital out (to U1.13(S3)) [ok]; GP8 = MUX_S2: digital out (to U1.14(S2)) [ok]; GP7 = MUX_S1: digital out (to U1.11(S1)) [ok]; GP6 = MUX_S0: digital out (to U1.10(S0)) [ok]; GP5 = ADC_CS: SPI chip select (U3) [ok]; GP4 = ADC_MISO: SPI data in (U3) [ok]; GP3 = ADC_MOSI: SPI data out (U3) [ok]; GP2 = ADC_SCK: SPI clock (U3) [ok]; GP1 = GP1: to connector J5.4(Pin_4) [ok]; GP0 = GP0: to connector J5.3(Pin_3) [ok]

| | |
|---|---|
| GP29 | GP29: to connector J5.8(Pin_8) [ok] |
| GP28 | GP28: to connector J5.7(Pin_7) [ok] |
| GP27 | GP27: to connector J5.6(Pin_6) [ok] |
| GP26 | GP26: to connector J5.5(Pin_5) [ok] |
| GP15 | SCL: to connector J1.3(Pin_3) [ok] |
| GP14 | SDA: to connector J1.4(Pin_4) [ok] |
| GP13 | LED_DATA: digital out (to U8.2) [ok] |
| GP12 | SR_DATA: digital in (from U5.9(Q7)) [ok] |
| GP11 | SR_LOAD: digital out (to U7.1(~{PL})) [ok] |
| GP10 | SR_CLK: digital out (to U7.2(CP)) [ok] |
| GP9 | MUX_S3: digital out (to U1.13(S3)) [ok] |
| GP8 | MUX_S2: digital out (to U1.14(S2)) [ok] |
| GP7 | MUX_S1: digital out (to U1.11(S1)) [ok] |
| GP6 | MUX_S0: digital out (to U1.10(S0)) [ok] |
| GP5 | ADC_CS: SPI chip select (U3) [ok] |
| GP4 | ADC_MISO: SPI data in (U3) [ok] |
| GP3 | ADC_MOSI: SPI data out (U3) [ok] |
| GP2 | ADC_SCK: SPI clock (U3) [ok] |
| GP1 | GP1: to connector J5.4(Pin_4) [ok] |
| GP0 | GP0: to connector J5.3(Pin_3) [ok] |

Basis: part model parts/rp2350-zero.yaml (verified against datasheet): pin capabilities; use inferred from what else is on each net.

### 5 supply rail(s) with a known voltage

`power.rails` · nets: +3V3, +5V, AVDD, OLED1_P2, OLED2_P2 · confidence: medium

+3V3 3.135-3.465 V (A1 3V3 output); +5V 4.75-5.25 V (net name); AVDD 3.135-3.465 V (+3V3 through FB1); OLED1_P2 3.135-3.465 V (+3V3 through JP2); OLED2_P2 3.135-3.465 V (+3V3 through JP4)

Basis: regulator models, net names, boardlint.yaml; override with rails: in boardlint.yaml.

### A1.3(3V3) supplies +3V3: 0 of 800 mA accounted for

`power.source_pin` · parts: A1 · nets: +3V3 · confidence: medium

A1 (RP2350-Zero).

| | |
|---|---|
| pin | A1.3(3V3) |
| limit_mA | 800.0 |
| load_max_mA | 0.2 |
| loads | U7 0.08 mA, U6 0.08 mA, U5 0.08 mA |
| not_counted | none |

Basis: part model parts/rp2350-zero.yaml (verified against datasheet).

### 32 capacitor(s) on known rails carry no voltage rating in the schematic

`ratings.passives` · confidence: high

Add a Voltage property (or put it in the value, e.g. '10uF 16V') and they will be checked.

### 20 of 20 addressable LED(s) latch data in simulation

`sim.led_chain` · parts: D1 · confidence: high

Position along each data line, as simulated: from D1: D1, D2, ... D20.

Basis: behavioural Verilog model (boardlint/sim/verilog/serial_led.v) wired from the netlist.

### Chip select ADC_CS has no pull-up

`spi.bus` · parts: U3 · nets: ADC_CS · confidence: medium

U3.10(~{CS}/SHDN) floats while the MCU is in reset or booting; a 10k pull-up keeps the part deselected. It matters most when the bus is shared.

## Coverage

| Check | Status | |
|---|---|---|
| `clock.source` | ran | 0 finding(s), 0.00 s |
| `decoupling.per_part` | ran | 1 finding(s), 0.00 s |
| `decoupling.regulator_caps` | ran | 0 finding(s), 0.00 s |
| `footprint.pin_map` | ran | 0 finding(s), 0.00 s |
| `i2c.bus` | ran | 4 finding(s), 0.11 s |
| `layout.coupling` | ran | 2 finding(s), 3.49 s |
| `layout.impedance` | ran | 4 finding(s), 0.48 s |
| `layout.ir_drop` | ran | 1 finding(s), 2.49 s |
| `layout.return_path` | ran | 1 finding(s), 1.87 s |
| `layout.track_current` | ran | 1 finding(s), 0.00 s |
| `led.chain` | ran | 2 finding(s), 0.00 s |
| `load.inductive` | ran | 0 finding(s), 0.00 s |
| `mcu.alt_function` | ran | 0 finding(s), 0.00 s |
| `mcu.pin_use` | ran | 1 finding(s), 0.00 s |
| `mcu.strapping` | ran | 0 finding(s), 0.00 s |
| `net.name_mismatch` | ran | 0 finding(s), 0.00 s |
| `pin.floating_control` | ran | 0 finding(s), 0.00 s |
| `pin.name_voltage` | ran | 0 finding(s), 0.00 s |
| `pin.requirements` | ran | 0 finding(s), 0.00 s |
| `pin.strap_strength` | ran | 0 finding(s), 0.00 s |
| `polarity.polarised_parts` | ran | 0 finding(s), 0.00 s |
| `power.budget` | ran | 0 finding(s), 0.00 s |
| `power.droop` | ran | 0 finding(s), 0.00 s |
| `power.logic_level` | ran | 0 finding(s), 0.00 s |
| `power.pin_voltage` | ran | 0 finding(s), 0.01 s |
| `power.rails` | ran | 1 finding(s), 0.00 s |
| `power.regulator` | ran | 0 finding(s), 0.00 s |
| `power.source_pin` | ran | 2 finding(s), 0.00 s |
| `power.supply_range` | ran | 0 finding(s), 0.00 s |
| `ratings.fets` | ran | 0 finding(s), 0.00 s |
| `ratings.passives` | ran | 1 finding(s), 0.00 s |
| `reset.circuit` | ran | 0 finding(s), 0.00 s |
| `sim.i2c` | ran | 0 finding(s), 0.00 s |
| `sim.led_chain` | ran | 1 finding(s), 0.05 s |
| `spi.bus` | ran | 1 finding(s), 0.00 s |
| `sync.schematic_board` | ran | 0 finding(s), 0.00 s |
| `uart.direction` | ran | 0 finding(s), 0.00 s |
| `usb.wiring` | ran | 0 finding(s), 0.00 s |

## Part models

| Parts | Value | Model | Verified against datasheet |
|---|---|---|---|
| A1 | RP2350-Zero | rp2350-zero | yes |
| D1, D10, D11, D12 +16 | SK6812MINI-RV | sk6812mini-rv | yes |
| ENC1 | EC11E15244B2 | **none: heuristics only** |  |
| J1 | OLED1 | **none: heuristics only** |  |
| J2 | OLED2 | **none: heuristics only** |  |
| J3 | PEDAL1 | **none: heuristics only** |  |
| J4 | PEDAL2 | **none: heuristics only** |  |
| J5 | SPARE_IO | **none: heuristics only** |  |
| SW1, SW10, SW11, SW12 +16 | 6x6 tact | **none: heuristics only** |  |
| U1 | CD74HC4067SM96 | cd74hc4067 | yes |
| U3 | MCP3208T-CI/SL | mcp3208 | yes |
| U4 | MCP6002T-I/SN | mcp6002 | yes |
| U5, U6, U7 | 74HC165D | 74hc165 | yes |
| U8 | 74AHCT1G125GV | 74ahct1g125 | yes |

## Known issues of the parts used

From errata sheets and forums, recorded in the part models. Not checked against this design.

- **RP2350-Zero** (usb-port-feeds-5v-pad): The 5V pad is the USB connector's VBUS with nothing in between, so loads on it (LED chains) add directly to the port current and there is no fuse or back-feed protection on the module. Source: https://files.waveshare.com/wiki/RP2350-Zero/RP2350_Zero.pdf
- **RP2350-Zero** (rp2350-e9-pull-down): RP2350-E9: with the pad input enabled, a Bank 0 GPIO left in the undefined logic region sources about 120 uA and sits near 2.2 V, so the internal pull-down cannot pull it low; an external pull-down must be 8.2 k or less. Fixed by RP2350 A3; the stepping fitted to a given module is not stated by Waveshare. Source: RP2350 datasheet release 9, appendix D.5.1 p.1358
- **RP2350-Zero** (spi-csn-pulses-between-words): With the hardware SPI CSn function and SPO = 0, SPH = 0, the chip select pulses high between every data word of a continuous transfer; a peripheral that needs chip select held low across several bytes (an MCP3208 24-clock frame) must use SPH = 1 or a plain GPIO as chip select. Source: RP2350 datasheet release 9, section 12.3.4.10 (Motorola SPI format with SPO=0, SPH=0)
