# boardlint review: tinytapeout-demo + breakout-gf-cob

**0 errors, 3 warnings, 15 notes.** 298 components, 150 nets; netlist from the schematic.

- 112 connector contacts join the two boards

## Warnings

### [baseboard] /project_clk is electrically long: 55 mm end to end, 347 ps one way

`layout.impedance` · parts: U6 · nets: /project_clk, ext_project_clk · confidence: low

clock. 55 mm between its furthest pads (56 mm routed in all). For a 2 ns edge a trace acts as a transmission line beyond about 53 mm (delay over one sixth of the rise time). Nothing terminates it: expect overshoot and ringing at the far end. On a clock that can be seen as a second edge. A 22 to 47 ohm resistor at the driver is the usual fix. Line impedance about 51 ohm.

| | |
|---|---|
| end_to_end_mm | 55.3 |
| routed_mm | 55.8 |
| delay_ps | 347 |
| z0 | 51 |
| assumed_rise_ns | 2.0 |
| stack_up | from the board file |

Basis: microstrip / stripline formulas on the stack-up; rise time is an assumption (signals: rise_ns in boardlint.yaml).

### C30, C32: the value says 14pF, the part number CC0402CRNPO9BN4R0 is 4pF

`bom.value_mpn` · parts: C30, C32 · confidence: medium

The part number is what gets ordered and fitted; the value field is what a reader, and every calculation in this report, goes by. One of the two is out of date.

| | |
|---|---|
| value_field | 14pF |
| part_number | CC0402CRNPO9BN4R0 |
| part_number_decodes_to | 4pF |

Basis: value codes in the part numbers of common resistor and capacitor series.

### 2 supply net(s) have no known voltage

`power.rails` · nets: /RP2350/VREG_AVDD, /RP2350/VREG_LX · confidence: high

/RP2350/VREG_AVDD, /RP2350/VREG_LX: voltage-dependent checks skip them. Declare them under rails: in boardlint.yaml.

## Notes

### 112 connector pads of the carrier line up with the baseboard's

`mate.geometry` · parts: J5, carrier/J2, carrier/J3 · confidence: high

Carrier not turned; pads paired by position, largest offset 0.050 mm. 

| | |
|---|---|
| pads_paired | 112 |
| baseboard_connectors | J5 |
| carrier_connectors | J2, J3 |
| carrier_orientation | not turned |
| largest_offset_mm | 0.05 |
| pairing_tolerance_mm | 0.15 |
| baseboard_side | F |
| carrier_side | B |

Basis: pad positions in the two board files.

### 1 contact(s) are connected on one board only

`mate.pins` · parts: J5 · confidence: high

/res_extra at J2.60 (carrier only).

Basis: paired pads.

### res / res: the two boards number the same signals 1 apart

`mate.pins` · parts: J5 · confidence: medium

Baseboard RES0 to RES2 meet carrier RES1 to RES3. The copper is one-to-one; only the names differ. Worth knowing when reading the two schematics or writing firmware against either.

Basis: paired pads; names on each board.

### Connector map: 70 contacts other than ground

`mate.pins` · parts: J5 · confidence: high

L1 +3V3 = J2.1 +3V3; L2 /A = J2.2 /an0; L4 /B = J2.4 /an1; L5 uio0 = J2.5 /uio0; L6 /C = J2.6 /an2; L7 uio1 = J2.7 /uio1; L9 uio2 = J2.9 /uio2; R2 VBUS = J3.2 +5V; R3 /uo_out7 = J3.3 /uout7; R4 VBUS = J3.4 +5V; R5 /uo_out6 = J3.5 /uout6; R7 /uo_out5 = J3.7 /uout5; R8 +3V3 = J3.8 +3V3; R9 /uo_out4 = J3.9 /uout4; L10 /D = J2.10 /an3; L12 /E = J2.12 /an4; L13 uio3 = J2.13 /uio3; L14 /F = J2.14 /an5; L15 /uio4 = J2.15 /uio4; L17 /uio5 = J2.17 /uio5; L18 /G = J2.18 /an6; L20 /H = J2.20 /an7; L21 /uio6 = J2.21 /uio6; L22 /J = J2.22 /an8; L23 /uio7 = J2.23 /uio7; L26 /K = J2.26 /an9; L28 /L = J2.28 /an10; L30 /M = J2.30 /an11; L31 ui_in0 = J2.31 /uin0; L33 ui_in1 = J2.33 /uin1; L34 /N = J2.34 /an12; L36 /P = J2.36 /an13; L37 ui_in2 = J2.37 /uin2; L38 /Q = J2.38 /an14; L39 ui_in3 = J2.39 /uin3; L41 /ui_in4 = J2.41 /uin4; L42 /R = J2.42 /an15; L44 /S = J2.44 /an16; L45 /ui_in5 = J2.45 /uin5; L46 /T = J2.46 /an17; L47 /ui_in6 = J2.47 /uin6; L49 /ui_in7 = J2.49 /uin7; L50 /U = J2.50 /an18; L52 /V = J2.52 /an19; L53 ~{project_rst} = J2.53 /~{p_rst}; L54 /W = J2.54 /an20; L57 /project_clk = J2.57 /p_clk; L58 /X = J2.58 /an21; L60 - = J2.60 /res_extra; R10 +3V3 = J3.10 +3V3; R13 uo_out3 = J3.13 /uout3; R15 uo_out2 = J3.15 /uout2; R16 /mng7 = J3.16 /mngIO7; R17 uo_out1 = J3.17 /uout1; R18 /mng6 = J3.18 /mngIO6; R19 uo_out0 = J3.19 /uout0; R22 /mng5 = J3.22 /mngIO5; R26 /mng4 = J3.26 /mngIO4; R29 res4 = J3.29 /reserved4; R30 /mng3 = J3.30 /mngIO3; R31 res3 = J3.31 /reserved3; R35 res2 = J3.35 /RES3; R36 /mng2 = J3.36 /mngIO2; R37 res1 = J3.37 /RES2; R39 res0 = J3.39 /RES1; R40 /mng1 = J3.40 /mngIO1; R42 /mng0 = J3.42 /mngIO0; R43 ~{ctrl_sel_rst} = J3.43 /rst_n; R46 ctrl_ena = J3.46 /enable; R47 ctrl_sel_inc = J3.47 /increment

| | |
|---|---|
| ground_contacts | 29 |
| supply_contacts_agreeing | 5 |

Basis: paired pads and each board's netlist.

### [baseboard] J5: footprint pad(s) L25, L29, L60, R14, R23, R24, R25, R27 have no pin on the symbol

`footprint.pin_map` · parts: J5 · confidence: medium

J5 (TT_HRS_BREAKOUT_REVB), symbol TinyTapeout:TT_HRS_BREAKOUT_REVB, footprint TinyTapeout:TT_HRS_CARRIER_REVC. They are unconnected on the board. Fine for mounting tabs; a mistake if the part has a function there (exposed pad, second row).

Basis: pin numbers in the schematic symbol against pad numbers in the board file.

### [baseboard] Net classes used for coupling: 13 aggressor, 7 victim net(s)

`layout.coupling` · confidence: medium

Aggressors: /RP2350/CLKIN, /RP2350/CLKO2, /RP2350/CLKOUT, /RP2350/QSPI_SCK, /RP2350/USBPi_+, /RP2350/USBPi_-, /man_clk, /man_clk_trig, /project_clk, Net-(R14-Pad2), ext_project_clk, usb_d+, usb_d-. Victims: /ADC1, /ADC2, /ADC3, /ADC4, /ADC5, /RP2350/ADC6, /RP2350/ADC7.

### [baseboard] Line parameters of 8 fast net(s)

`layout.impedance` · confidence: low

/RP2350/USBPi_+: 68 mm, 0.2 mm on B.Cu, 61 ohm, 425 ps, 6.9 pF, 97% over a plane, 2 vias; /RP2350/USBPi_-: 67 mm, 0.2 mm on B.Cu, 61 ohm, 419 ps, 6.8 pF, 98% over a plane, 2 vias; /project_clk: 56 mm, 0.3 mm on F.Cu, 51 ohm, 350 ps, 6.8 pF, 99% over a plane, 0 vias; /man_clk: 36 mm, 0.2 mm on B.Cu, 60 ohm, 226 ps, 3.6 pF, 95% over a plane, 2 vias; /RP2350/QSPI_SCK: 16 mm, 0.2 mm on F.Cu, 62 ohm, 99 ps, 1.5 pF, 88% over a plane, 0 vias; /man_clk_trig: 13 mm, 0.25 mm on F.Cu, 55 ohm, 82 ps, 1.3 pF, 79% over a plane, 2 vias; /RP2350/CLKIN: 9 mm, 0.2 mm on F.Cu, 61 ohm, 58 ps, 1.0 pF, 100% over a plane, 0 vias; /RP2350/CLKO2: 7 mm, 0.2 mm on F.Cu, 61 ohm, 43 ps, 0.7 pF, 100% over a plane, 0 vias.

| | |
|---|---|
| stack_up | F.Cu / 0.1855 mm er 4.74, In1.Cu / 1.03 mm er 4.6, In2.Cu / 0.1855 mm er 4.74 / B.Cu |

Basis: microstrip / stripline formulas on the stack-up.

### [baseboard] USB pair: about 117 ohm differential, 1.0 mm length mismatch

`layout.impedance` · nets: /RP2350/USBPi_+, /RP2350/USBPi_-, usb_d+, usb_d- · confidence: low

D+ 68 mm, D- 67 mm (mismatch 1.0 mm). Routed as a pair for 67 mm at a 0.50 mm gap: about 117 ohm differential; USB asks for 90 ohm +/- 15 %. At full speed (12 Mbit/s) this is tolerant; at high speed (480 Mbit/s) both the impedance and a mismatch over about 1 mm matter.

| | |
|---|---|
| d_plus_mm | 68.5 |
| d_minus_mm | 67.4 |
| mismatch_mm | 1.0 |
| routed_as_a_pair_mm | 66.7 |
| stack_up | from the board file |
| gap_mm | 0.5 |
| z_diff | 117 |

Basis: edge-coupled microstrip formula on the stack-up.

### [baseboard] 40 net(s) could not be compared between schematic and board

`sync.schematic_board` · confidence: low

The schematic passes signals between sheets as buses, which the built-in netlister does not expand, so those nets look different from the board's. This run uses the board's netlist. KiCad's own schematic-parity check is the one to trust here.

Basis: comparison of the schematic netlist and the board file.

### [carrier] Net classes used for coupling: 1 aggressor, 22 victim net(s)

`layout.coupling` · confidence: medium

Aggressors: /p_clk. Victims: /an0, /an1, /an10, /an11, /an12, /an13, /an14, /an15, /an16, /an17, /an18, /an19, /an2, /an20, /an21, /an3, /an4, /an5, /an6, /an7....

### [carrier] Line parameters of 1 fast net(s)

`layout.impedance` · confidence: low

/p_clk: 23 mm, 0.16 mm on F.Cu, 66 ohm, 139 ps, 2.1 pF, 99% over a plane, 1 vias.

| | |
|---|---|
| stack_up | F.Cu / 0.1855 mm er 4.74, In1.Cu / 1.03 mm er 4.6, In2.Cu / 0.1855 mm er 4.74 / B.Cu |

Basis: microstrip / stripline formulas on the stack-up.

### Crystal Y1: load capacitance about 6 pF with stray

`clock.source` · parts: Y1 · confidence: medium

Compare with the CL in the crystal's datasheet.

| | |
|---|---|
| load_caps | 4pF + 4pF (from the part numbers; the value fields differ) |
| series_value | 2pF |
| with_3_to_5pF_stray | 5.0 to 7.0 pF |

### 12 supply rail(s) with a known voltage

`power.rails` · nets: +1V1, +3V3, /vfused, VBUS, VBUSRW, carrier//VCOREIN · confidence: medium

+1V1 1.045-1.155 V (net name); +3V3 3.25-3.349 V (U1 TLV1117LV33 output); /vfused 4.4-5.5 V (VBUS through FB1); VBUS 4.4-5.5 V (USB VBUS range (name)); VBUSRW 4.4-5.5 V (USB VBUS range (name)); carrier//VCOREIN 3.25-3.349 V (+3V3 through carrier/R3); carrier//VDIN 3.25-3.349 V (+3V3 through carrier/R7); carrier/VAA 3.25-3.349 V (carrier/VIO_{REG} through carrier/R9); carrier/VCORE_{REG} 3.25-3.349 V (carrier//VCOREIN through carrier/R2); carrier/VDD_{CORE} 3.25-3.349 V (carrier/VCORE_{REG} through carrier/R4); carrier/VDD_{IO} 3.25-3.349 V (carrier/VIO_{REG} through carrier/R8); carrier/VIO_{REG} 3.25-3.349 V (carrier//VDIN through carrier/R6)

Basis: regulator models, net names, boardlint.yaml; override with rails: in boardlint.yaml.

### U1 load on +3V3 is unknown

`power.regulator` · parts: U1 · nets: +3V3 · confidence: high

No part on the rail has a current in its model (U2, U3, U5, U6, U7 not counted): dropout and thermal checks skipped.

### 49 capacitor(s) on known rails carry no voltage rating in the schematic

`ratings.passives` · confidence: high

Add a Voltage property (or put it in the value, e.g. '10uF 16V') and they will be checked.

## Coverage

| Check | Status | |
|---|---|---|
| `mate.geometry` | ran |  |
| `mate.pins` | ran |  |
| `footprint.pin_map (baseboard)` | ran | 1 finding(s), 0.00 s |
| `layout.coupling (baseboard)` | ran | 1 finding(s), 1.60 s |
| `layout.impedance (baseboard)` | ran | 3 finding(s), 0.28 s |
| `layout.ir_drop (baseboard)` | ran | 0 finding(s), 1.42 s |
| `layout.return_path (baseboard)` | ran | 0 finding(s), 0.78 s |
| `layout.track_current (baseboard)` | ran | 0 finding(s), 0.00 s |
| `sync.schematic_board (baseboard)` | ran | 1 finding(s), 0.00 s |
| `footprint.pin_map (carrier)` | ran | 0 finding(s), 0.00 s |
| `layout.coupling (carrier)` | ran | 1 finding(s), 0.03 s |
| `layout.impedance (carrier)` | ran | 1 finding(s), 0.01 s |
| `layout.ir_drop (carrier)` | ran | 0 finding(s), 0.00 s |
| `layout.return_path (carrier)` | ran | 0 finding(s), 0.01 s |
| `layout.track_current (carrier)` | ran | 0 finding(s), 0.00 s |
| `sync.schematic_board (carrier)` | ran | 0 finding(s), 0.00 s |
| `bom.value_mpn` | ran | 1 finding(s), 0.00 s |
| `clock.source` | ran | 1 finding(s), 0.00 s |
| `decoupling.per_part` | ran | 0 finding(s), 0.00 s |
| `decoupling.regulator_caps` | ran | 0 finding(s), 0.00 s |
| `i2c.bus` | ran | 0 finding(s), 0.00 s |
| `led.chain` | ran | 0 finding(s), 0.00 s |
| `load.inductive` | ran | 0 finding(s), 0.00 s |
| `mcu.alt_function` | ran | 0 finding(s), 0.00 s |
| `mcu.pin_use` | ran | 0 finding(s), 0.00 s |
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
| `power.pin_voltage` | ran | 0 finding(s), 0.04 s |
| `power.rails` | ran | 2 finding(s), 0.00 s |
| `power.regulator` | ran | 1 finding(s), 0.00 s |
| `power.source_pin` | ran | 0 finding(s), 0.00 s |
| `power.supply_range` | ran | 0 finding(s), 0.00 s |
| `power.unpowered` | ran | 0 finding(s), 0.00 s |
| `ratings.fets` | ran | 0 finding(s), 0.00 s |
| `ratings.passives` | ran | 1 finding(s), 0.00 s |
| `reset.circuit` | ran | 0 finding(s), 0.00 s |
| `sim.i2c` | ran | 0 finding(s), 0.00 s |
| `sim.led_chain` | ran | 0 finding(s), 0.00 s |
| `spi.bus` | ran | 0 finding(s), 0.00 s |
| `uart.direction` | ran | 0 finding(s), 0.00 s |
| `usb.wiring` | ran | 0 finding(s), 0.00 s |

## Part models

| Parts | Value | Model | Verified against datasheet |
|---|---|---|---|
| D1, D2 | TVS | 0603esda-aec1 | yes |
| D10, D11, D12, D13 +18 | 5VTVS | sp3022-01etg-ms | yes |
| D3, D4, D5 | Yellow | **none: heuristics only** |  |
| F1 | 350mA | polyfuse-0805-0.35a | yes |
| J1 | USB_C | **none: heuristics only** |  |
| J10, J4 | Conn_01x04 | **none: heuristics only** |  |
| J11, J8 | Conn_01x02 | **none: heuristics only** |  |
| J12 | Conn_02x05_Odd_Even | **none: heuristics only** |  |
| J13 | Conn_02x16_Odd_Even | **none: heuristics only** |  |
| J14, J15, J16 | 613012243121 | **none: heuristics only** |  |
| J17, J6, J9 | Conn_01x03 | **none: heuristics only** |  |
| J2 | DF12NB(5.0)-50DP-0.5V(51) | **none: heuristics only** |  |
| J3 | DF12NB(5.0)-60DP-0.5V(51) | **none: heuristics only** |  |
| J5 | TT_HRS_BREAKOUT_REVB | **none: heuristics only** |  |
| J7 | Conn_01x16 | **none: heuristics only** |  |
| Q1 | DMG2305UX-7 | dmg2305ux | yes |
| SW1 | 193-8MSR | **none: heuristics only** |  |
| SW2, SW3, SW4 | 434121025816 | **none: heuristics only** |  |
| U1 | TLV1117LV33 | tlv1117lv33 | yes |
| U2, U3 | NC7SP14P5X | **none: heuristics only** |  |
| U4 | 157112V12700 | **none: heuristics only** |  |
| U5 | MCP6001-OT | **none: heuristics only** |  |
| U6 | RP2350-QFN80 | **none: heuristics only** |  |
| U7 | W25Q32JVSS | **none: heuristics only** |  |
| carrier/J1 | Conn_01x12 | **none: heuristics only** |  |
| carrier/J2 | DF12NB-60DS-0.5V_51 | **none: heuristics only** |  |
| carrier/J3 | DF12NB-50DS-0.5V_51 | **none: heuristics only** |  |
| carrier/U1, carrier/U2 | AP2112K-3.3 | ap2112k-3.3 | yes |
| carrier/U3 | TT_GF_0p2_ASIC | tt-asic-gf180-cob | no |
| carrier/U4 | 24LC02 | **none: heuristics only** |  |

## Known issues of the parts used

From errata sheets and forums, recorded in the part models. Not checked against this design.

- **DMG2305UX-7** (lcsc-c5261054-is-not-the-diodes-part): LCSC C5261054 is sold as "DMG2305UX-7" but is made by HXY MOSFET, not Diodes. Its own datasheet gives a +/-12 V gate rating (Diodes +/-8 V), threshold -0.4 to -1.0 V (Diodes -0.5 to -0.9 V), RDS(on) 45 / 60 / 85 mOhm max at -4.5 / -2.5 / -1.8 V (Diodes 52 / 100 / 200), PD 1.31 W and 120 C/W junction to ambient (Diodes 1.4 W, 90 C/W). The genuine Diodes part is LCSC C150470. A circuit that leans on the exact threshold or RDS(on), such as a current source or a linear-region pass element, should be checked against the part that is actually fitted. Source: https://www.lcsc.com/product-detail/C5261054.html and its datasheet https://datasheet.lcsc.com/datasheet/pdf/b91d074ff27bcf2102159ebbd6d79f51.pdf (HXY DMG2305UX-7, 6 pages, p.1-2 read 2026-11-25)
- **TLV1117LV33** (alternate-az1117c-not-equivalent): The alternate AZ1117CH-3.3TRG1 (Diodes AZ1117C) fits the footprint but is a different kind of regulator: it requires at least 10 uF on the output (TLV1117LV: 1 uF), drops 1.3 V max at 0.8 A (TLV1117LV: 0.7 V max at 1 A) so 3.3 V out needs about 4.6 V in, draws 4 mA typ / 6 mA max with no load (TLV1117LV: 0.05 / 0.1 mA) and accepts up to 15 V in (TLV1117LV: 5.5 V, 6 V absolute maximum). Check the output capacitor and the input headroom for whichever part is fitted. Source: Diodes AZ1117C DS36676 Rev. 5 - 2, note 4 p.3, ratings p.4, AZ1117C-3.3 table p.7; TI SBVS160C p.4-5, p.13
- **AP2112K-3.3** (foldback-start-up): With a current load already on the output before the part is enabled (multiple or negative supplies, a current-source load) the fold-back current limit, 50 mA at VOUT = 0, may prevent start-up. Source: Diodes AP2112 DS39724 Rev. 2 - 2, Application Note p.11
- **AP2112K-3.3** (lcsc-c23380830-is-not-the-diodes-part): LCSC C23380830 is sold as "AP2112K-3.3TRG1" but is made by TECH PUBLIC, not Diodes, and its own datasheet differs from this model: input 1.2 to 5.5 V (Diodes 2.5 to 6.0 V), EN high threshold 2 V max and low 0.6 V min (Diodes 1.5 V and 0.4 V), EN input current 10 nA typ / 100 nA max with no pull-down mentioned (Diodes 3 MOhm pull-down), ground current 10 uA typ, accuracy +/-2 %, dropout 0.32 V typ at 600 mA with no maximum, current limit 601 mA min / 1100 mA typ, junction to ambient 250 C/W (Diodes 184), discharge 100 Ohm typ. Absolute maximum VIN 6.5 V, VOUT and EN 6 V. Source: https://www.lcsc.com/product-detail/C23380830.html and its datasheet https://datasheet.lcsc.com/datasheet/pdf/6334215d19505e864d16d9e12e383172.pdf (TECH PUBLIC AP2112K Series, 9 scanned pages; p.1 to 5 read as images, 2026-11-25)
