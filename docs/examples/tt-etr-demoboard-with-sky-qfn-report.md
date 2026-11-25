# boardlint review: tinytapeout-demo + breakout-sky-qfn

**0 errors, 6 warnings, 22 notes.** 267 components, 144 nets; netlist from the schematic.

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

### [baseboard] U5 supply +3V3: nearest 10nF+ capacitor is 10.4 mm away

`decoupling.per_part` · parts: U5, C12 · nets: +3V3 · confidence: high

U5 (MCP6001-OT) wants 1 within 2 mm of its supply pin; closest are C12 at 10.4 mm, C13 at 12.0 mm, C11 at 19.4 mm (pad to pad, straight line). Distance adds loop inductance: about 1 nH per mm of trace.

| | |
|---|---|
| required_mm | 2.0 |
| nearest_mm | 10.43 |

Basis: part model parts/mcp6001.yaml (verified against datasheet): local bypass 0.01 uF to 0.1 uF within 2 mm of the VDD pin (section 4.4); distance measured on the board.

### [baseboard] U1 has no output capacitor within 10 mm: the nearest of 500nF or more is C4 at 17 mm

`decoupling.regulator_caps` · parts: U1, C4 · nets: +3V3 · confidence: low

U1 (TLV1117LV33) on +3V3. The rail carries 42.5uF in all, so the amount is there; the distance adds about 1 nH per millimetre in series with it, which is what a regulator's stability figures do not allow for. Measured from the nearest pad of the pin, tab included.

| | |
|---|---|
| required | 500nF |
| on_the_rail | 42.5uF |
| nearest_mm | 17.1 |

Basis: part model parts/tlv1117lv33.yaml (verified against datasheet); the 10 mm distance is a rule of thumb, not a datasheet figure.

### C30, C32: the value says 14pF, the part number CC0402CRNPO9BN4R0 is 4pF

`bom.value_mpn` · parts: C30, C32 · confidence: medium

The part number is what gets ordered and fitted; the value field is what a reader, and every calculation in this report, goes by. One of the two is out of date.

| | |
|---|---|
| value_field | 14pF |
| part_number | CC0402CRNPO9BN4R0 |
| part_number_decodes_to | 4pF |

Basis: value codes in the part numbers of common resistor and capacitor series.

### ctrl_ena rests at 0.304 V: a pull-up and a pull-down oppose each other

`power.logic_level` · parts: U6, R38, carrier/R9 · nets: ctrl_ena · confidence: high

R38 (10k) pulls it to +3V3 and carrier/R9 (1k) pulls it to ground, so undriven it sits at 0.304 V, a logic low at U6.77(GPIO0). U6.77(GPIO0) can drive the line, so it works; but the pull-up does nothing except waste 0.30 mA, and whoever fitted it expected a high when nothing drives the line.

| | |
|---|---|
| divider | R38 10k / carrier/R9 1k from +3V3 |
| net_v | 0.295-0.304 V |
| vih | 2.0 |

Basis: resistor values on the net.

### ~{ctrl_sel_rst} rests at 0.304 V: a pull-up and a pull-down oppose each other

`power.logic_level` · parts: U6, R39, carrier/R10 · nets: ~{ctrl_sel_rst} · confidence: high

R39 (10k) pulls it to +3V3 and carrier/R10 (1k) pulls it to ground, so undriven it sits at 0.304 V, a logic low at U6.78(GPIO1). U6.78(GPIO1) can drive the line, so it works; but the pull-up does nothing except waste 0.30 mA, and whoever fitted it expected a high when nothing drives the line.

| | |
|---|---|
| divider | R39 10k / carrier/R10 1k from +3V3 |
| net_v | 0.295-0.304 V |
| vih | 2.0 |

Basis: resistor values on the net.

## Notes

### 112 connector pads of the carrier line up with the baseboard's

`mate.geometry` · parts: J5, carrier/J1, carrier/J3 · confidence: high

Carrier not turned; pads paired by position, largest offset 0.050 mm. 

| | |
|---|---|
| pads_paired | 112 |
| baseboard_connectors | J5 |
| carrier_connectors | J1, J3 |
| carrier_orientation | not turned |
| largest_offset_mm | 0.05 |
| pairing_tolerance_mm | 0.15 |
| baseboard_side | F |
| carrier_side | B |

Basis: pad positions in the two board files.

### 8 signal(s) of one board are grounded by the other

`mate.pins` · parts: J5 · confidence: medium

/A (baseboard) at J5.L2(anA); /B (baseboard) at J5.L4(anB); /E (baseboard) at J5.L12(anE); /H (baseboard) at J5.L20(anH); /L (baseboard) at J5.L28(anL); /M (baseboard) at J5.L30(anM); /P (baseboard) at J5.L36(anP); /N (baseboard) at J5.L34(anN). Nothing with a push-pull output drives them, so this is harmless: the usual reason is a signal the other board does not use.

Basis: paired pads and each board's netlist.

### 1 contact(s) are connected on one board only

`mate.pins` · parts: J5 · confidence: high

/res_extra at J1.60 (carrier only).

Basis: paired pads.

### res / res: the two boards number the same signals 1 apart

`mate.pins` · parts: J5 · confidence: medium

Baseboard RES0 to RES2 meet carrier RES1 to RES3. The copper is one-to-one; only the names differ. Worth knowing when reading the two schematics or writing firmware against either.

Basis: paired pads; names on each board.

### Connector map: 70 contacts other than ground

`mate.pins` · parts: J5 · confidence: high

L1 +3V3 = J1.1 +3V3; L2 /A = J1.2 GND; L4 /B = J1.4 GND; L5 uio0 = J1.5 /uio0; L6 /C = J1.6 /an0; L7 uio1 = J1.7 /uio1; L9 uio2 = J1.9 /uio2; R2 VBUS = J3.2 +5V; R3 /uo_out7 = J3.3 /uout7; R4 VBUS = J3.4 +5V; R5 /uo_out6 = J3.5 /uout6; R7 /uo_out5 = J3.7 /uout5; R8 +3V3 = J3.8 +3V3; R9 /uo_out4 = J3.9 /uout4; L10 /D = J1.10 /an1; L12 /E = J1.12 GND; L13 uio3 = J1.13 /uio3; L14 /F = J1.14 /an2; L15 /uio4 = J1.15 /uio4; L17 /uio5 = J1.17 /uio5; L18 /G = J1.18 /an3; L20 /H = J1.20 GND; L21 /uio6 = J1.21 /uio6; L22 /J = J1.22 /an4; L23 /uio7 = J1.23 /uio7; L26 /K = J1.26 /an5; L28 /L = J1.28 GND; L30 /M = J1.30 GND; L31 ui_in0 = J1.31 /uin0; L33 ui_in1 = J1.33 /uin1; L34 /N = J1.34 GND; L36 /P = J1.36 GND; L37 ui_in2 = J1.37 /uin2; L38 /Q = J1.38 /an11; L39 ui_in3 = J1.39 /uin3; L41 /ui_in4 = J1.41 /uin4; L42 /R = J1.42 /an10; L44 /S = J1.44 /res_an16; L45 /ui_in5 = J1.45 /uin5; L46 /T = J1.46 /an9; L47 /ui_in6 = J1.47 /uin6; L49 /ui_in7 = J1.49 /uin7; L50 /U = J1.50 /an8; L52 /V = J1.52 /res_an19; L53 ~{project_rst} = J1.53 /p_rst; L54 /W = J1.54 /an7; L57 /project_clk = J1.57 /p_clk; L58 /X = J1.58 /an6; L60 - = J1.60 /res_extra; R10 +3V3 = J3.10 +3V3; R13 uo_out3 = J3.13 /uout3; R15 uo_out2 = J3.15 /uout2; R16 /mng7 = J3.16 /mngIO7; R17 uo_out1 = J3.17 /uout1; R18 /mng6 = J3.18 /mngIO6; R19 uo_out0 = J3.19 /uout0; R22 /mng5 = J3.22 /mngIO5; R26 /mng4 = J3.26 /mngIO4; R29 res4 = J3.29 /reserved4; R30 /mng3 = J3.30 /mngIO3; R31 res3 = J3.31 /reserved3; R35 res2 = J3.35 /RES3; R36 /mng2 = J3.36 /mngIO2; R37 res1 = J3.37 /RES2; R39 res0 = J3.39 /RES1; R40 /mng1 = J3.40 /mngIO1; R42 /mng0 = J3.42 /mngIO0; R43 ~{ctrl_sel_rst} = J3.43 /hd_c_rst_n; R46 ctrl_ena = J3.46 /c_ena; R47 ctrl_sel_inc = J3.47 /c_sel_inc

| | |
|---|---|
| ground_contacts | 29 |
| supply_contacts_agreeing | 5 |

Basis: paired pads and each board's netlist.

### [baseboard] J5: footprint pad(s) L25, L29, L60, R14, R23, R24, R25, R27 have no pin on the symbol

`footprint.pin_map` · parts: J5 · confidence: medium

J5 (TT_HRS_BREAKOUT_REVB), symbol TinyTapeout:TT_HRS_BREAKOUT_REVB, footprint TinyTapeout:TT_HRS_CARRIER_REVC. They are unconnected on the board. Fine for mounting tabs; a mistake if the part has a function there (exposed pad, second row).

Basis: pin numbers in the schematic symbol against pad numbers in the board file.

### [baseboard] Net classes used for coupling: 15 aggressor, 10 victim net(s)

`layout.coupling` · confidence: medium

Aggressors: /RP2350/CLKIN, /RP2350/CLKO2, /RP2350/CLKOUT, /RP2350/QSPI_SCK, /RP2350/QSPI_SD0, /RP2350/QSPI_SD1, /RP2350/USBPi_+, /RP2350/USBPi_-, /man_clk, /man_clk_trig, /project_clk, Net-(R14-Pad2), ext_project_clk, usb_d+.... Victims: /ADC1, /ADC2, /ADC3, /ADC4, /ADC5, /RP2350/ADC6, /RP2350/ADC7, Net-(C22-Pad1), Net-(Q1-S), Net-(U5-+).

### [baseboard] Line parameters of 10 fast net(s)

`layout.impedance` · confidence: low

/RP2350/USBPi_+: 68 mm, 0.2 mm on B.Cu, 61 ohm, 425 ps, 6.9 pF, 97% over a plane, 2 vias; /RP2350/USBPi_-: 67 mm, 0.2 mm on B.Cu, 61 ohm, 419 ps, 6.8 pF, 98% over a plane, 2 vias; /project_clk: 56 mm, 0.3 mm on F.Cu, 51 ohm, 350 ps, 6.8 pF, 99% over a plane, 0 vias; /man_clk: 36 mm, 0.2 mm on B.Cu, 60 ohm, 226 ps, 3.6 pF, 95% over a plane, 2 vias; /RP2350/QSPI_SD1: 21 mm, 0.2 mm on F.Cu, 62 ohm, 132 ps, 1.6 pF, 69% over a plane, 2 vias; /RP2350/QSPI_SD0: 17 mm, 0.22 mm on In1.Cu, 63 ohm, 113 ps, 1.1 pF, 43% over a plane, 2 vias; /RP2350/QSPI_SCK: 16 mm, 0.2 mm on F.Cu, 62 ohm, 99 ps, 1.5 pF, 88% over a plane, 0 vias; /man_clk_trig: 13 mm, 0.25 mm on F.Cu, 55 ohm, 82 ps, 1.3 pF, 79% over a plane, 2 vias; /RP2350/CLKIN: 9 mm, 0.2 mm on F.Cu, 61 ohm, 58 ps, 1.0 pF, 100% over a plane, 0 vias; /RP2350/CLKO2: 7 mm, 0.2 mm on F.Cu, 61 ohm, 43 ps, 0.7 pF, 100% over a plane, 0 vias.

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

### [baseboard] /RP2350/QSPI_SD0: 38% of its 17 mm has no ground or supply plane on the next layer

`layout.return_path` · nets: /RP2350/QSPI_SD0 · confidence: medium

/RP2350/QSPI_SD0 (SPI). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 9 stretch(es) without cover.

| | |
|---|---|
| length_mm | 17.4 |
| uncovered_mm | 6.6 |
| stretches | 9 |

Basis: filled ground and supply zones in the board file, sampled every 0.5 mm along the tracks.

### [baseboard] /RP2350/QSPI_SD1: 29% of its 21 mm has no ground or supply plane on the next layer

`layout.return_path` · nets: /RP2350/QSPI_SD1 · confidence: medium

/RP2350/QSPI_SD1 (SPI). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 6 stretch(es) without cover.

| | |
|---|---|
| length_mm | 20.6 |
| uncovered_mm | 5.9 |
| stretches | 6 |

Basis: filled ground and supply zones in the board file, sampled every 0.5 mm along the tracks.

### [baseboard] 40 net(s) could not be compared between schematic and board

`sync.schematic_board` · confidence: low

The schematic passes signals between sheets as buses, which the built-in netlister does not expand, so those nets look different from the board's. This run uses the board's netlist. KiCad's own schematic-parity check is the one to trust here.

Basis: comparison of the schematic netlist and the board file.

### [carrier] Net classes used for coupling: 1 aggressor, 12 victim net(s)

`layout.coupling` · confidence: medium

Aggressors: /p_clk. Victims: /an0, /an1, /an10, /an11, /an2, /an3, /an4, /an5, /an6, /an7, /an8, /an9.

### [carrier] Line parameters of 1 fast net(s)

`layout.impedance` · confidence: low

/p_clk: 25 mm, 0.22 mm on B.Cu, 57 ohm, 159 ps, 2.5 pF, 87% over a plane, 3 vias.

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

### U6 pin use: 61 pins in use (25 plain connector I/O not listed)

`mcu.pin_use` · parts: U6 · confidence: medium

GPIO4 = /mng1: I2C SDA (carrier/U3) [ok]; GPIO5 = /mng2: I2C SCL (carrier/U3) [ok]; GPIO11 = /RPLED: digital out (to D5.2(A)) [ok]; GPIO12 = /IREFPWM: to R34.2 [ok]; GPIO13 = /RP2350/GPIO13: unused [ok]; GPIO14 = ~{project_rst}: reset out (carrier/U4) [ok]; GPIO15 = /man_clk: digital in (from U2.4) [ok]; XIN = /RP2350/CLKIN: to Y1.1 [ok]; XOUT = /RP2350/CLKOUT: to Y1.3 [ok]; SWCLK = /RP2350/SWCLK: unused [ok]; SWDIO = /RP2350/SWDIO: unused [ok]; GPIO33 = uo_out0: digital in (from carrier/U4.62(uo_out[0])) [ok]; GPIO34 = uo_out1: digital in (from carrier/U4.2(uo_out[1])) [ok]; GPIO35 = uo_out2: digital in (from carrier/U4.3(uo_out[2])) [ok]; GPIO36 = uo_out3: digital in (from carrier/U4.4(uo_out[3])) [ok]; GPIO37 = /uo_out4: digital in (from carrier/U4.5(uo_out[4])) [ok]; GPIO38 = /uo_out5: digital in (from carrier/U4.6(uo_out[5])) [ok]; GPIO39 = /uo_out6: digital in (from carrier/U4.7(uo_out[6])) [ok]; GPIO40_ADC0 = /uo_out7: digital in (from carrier/U4.8(uo_out[7])) [ok]; GPIO41_ADC1 = /ADC1: analog in [ok: ADC1]; GPIO42_ADC2 = /ADC2: analog in [ok: ADC1]; GPIO43_ADC3 = /ADC3: analog in [ok: ADC1]; GPIO44_ADC4 = /ADC4: analog in [ok: ADC1]; GPIO45_ADC5 = /ADC5: analog in [ok: ADC1]; GPIO46_ADC6 = /RP2350/ADC6: analog in [ok: ADC1]; GPIO47_ADC7 = /RP2350/ADC7: analog in [ok: ADC1]; USB_DM = /RP2350/USBPi_-: USB D- (J1) [ok]; USB_DP = /RP2350/USBPi_+: USB D+ (J1) [ok]; QSPI_SD3 = /RP2350/QSPI_SD3: digital in (from U7.7(IO3)) [ok]; QSPI_SCLK = /RP2350/QSPI_SCK: SPI clock (U7) [ok]; QSPI_SD0 = /RP2350/QSPI_SD0: SPI data out (U7) [ok]; QSPI_SD2 = /RP2350/QSPI_SD2: digital in (from U7.3(IO2)) [ok]; QSPI_SD1 = /RP2350/QSPI_SD1: SPI data in (U7) [ok]; QSPI_SS = /BOOT: SPI chip select (U7) [ok; strapping pin]; GPIO0 = ctrl_ena: level of +3V3 through R38/carrier/R9 (analog or digital) [no ADC here: digital only]; GPIO1 = ~{ctrl_sel_rst}: reset out (carrier/U4) [ok]

| | |
|---|---|
| GPIO4 | /mng1: I2C SDA (carrier/U3) [ok] |
| GPIO5 | /mng2: I2C SCL (carrier/U3) [ok] |
| GPIO11 | /RPLED: digital out (to D5.2(A)) [ok] |
| GPIO12 | /IREFPWM: to R34.2 [ok] |
| GPIO13 | /RP2350/GPIO13: unused [ok] |
| GPIO14 | ~{project_rst}: reset out (carrier/U4) [ok] |
| GPIO15 | /man_clk: digital in (from U2.4) [ok] |
| XIN | /RP2350/CLKIN: to Y1.1 [ok] |
| XOUT | /RP2350/CLKOUT: to Y1.3 [ok] |
| SWCLK | /RP2350/SWCLK: unused [ok] |
| SWDIO | /RP2350/SWDIO: unused [ok] |
| GPIO33 | uo_out0: digital in (from carrier/U4.62(uo_out[0])) [ok] |
| GPIO34 | uo_out1: digital in (from carrier/U4.2(uo_out[1])) [ok] |
| GPIO35 | uo_out2: digital in (from carrier/U4.3(uo_out[2])) [ok] |
| GPIO36 | uo_out3: digital in (from carrier/U4.4(uo_out[3])) [ok] |
| GPIO37 | /uo_out4: digital in (from carrier/U4.5(uo_out[4])) [ok] |
| GPIO38 | /uo_out5: digital in (from carrier/U4.6(uo_out[5])) [ok] |
| GPIO39 | /uo_out6: digital in (from carrier/U4.7(uo_out[6])) [ok] |
| GPIO40_ADC0 | /uo_out7: digital in (from carrier/U4.8(uo_out[7])) [ok] |
| GPIO41_ADC1 | /ADC1: analog in [ok: ADC1] |
| GPIO42_ADC2 | /ADC2: analog in [ok: ADC1] |
| GPIO43_ADC3 | /ADC3: analog in [ok: ADC1] |
| GPIO44_ADC4 | /ADC4: analog in [ok: ADC1] |
| GPIO45_ADC5 | /ADC5: analog in [ok: ADC1] |
| GPIO46_ADC6 | /RP2350/ADC6: analog in [ok: ADC1] |
| GPIO47_ADC7 | /RP2350/ADC7: analog in [ok: ADC1] |
| USB_DM | /RP2350/USBPi_-: USB D- (J1) [ok] |
| USB_DP | /RP2350/USBPi_+: USB D+ (J1) [ok] |
| QSPI_SD3 | /RP2350/QSPI_SD3: digital in (from U7.7(IO3)) [ok] |
| QSPI_SCLK | /RP2350/QSPI_SCK: SPI clock (U7) [ok] |
| QSPI_SD0 | /RP2350/QSPI_SD0: SPI data out (U7) [ok] |
| QSPI_SD2 | /RP2350/QSPI_SD2: digital in (from U7.3(IO2)) [ok] |
| QSPI_SD1 | /RP2350/QSPI_SD1: SPI data in (U7) [ok] |
| QSPI_SS | /BOOT: SPI chip select (U7) [ok; strapping pin] |
| GPIO0 | ctrl_ena: level of +3V3 through R38/carrier/R9 (analog or digital) [no ADC here: digital only] |
| GPIO1 | ~{ctrl_sel_rst}: reset out (carrier/U4) [ok] |

Basis: part model parts/rp2350b.yaml (verified against datasheet): pin capabilities; use inferred from what else is on each net.

### U6.77(GPIO0) can only read ctrl_ena as a digital level

`mcu.pin_use` · parts: U6 · nets: ctrl_ena · confidence: medium

U6 (RP2350-QFN80): level of +3V3 through R38/carrier/R9 (analog or digital). The pin has no ADC channel. Fine if firmware only tests high or low; to measure the voltage use one of GPIO40, GPIO41, GPIO42, GPIO43, GPIO44, GPIO45, GPIO46, GPIO47, GPIO40_ADC0, GPIO41_ADC1, GPIO42_ADC2, GPIO43_ADC3, GPIO44_ADC4, GPIO45_ADC5, GPIO46_ADC6, GPIO47_ADC7.

Basis: part model parts/rp2350b.yaml (verified against datasheet): ADC channel table.

### +3V3 holds 3.30 V or better through its worst load step

`power.droop` · parts: U1 · nets: +3V3, VBUS · confidence: low

U1 (TLV1117LV33). U6 (RP2350-QFN80) needs 3.135 V. Simulated in 2 corner(s).

| | |
|---|---|
| load_step | 0 -> 25 mA in 10 us (U7 25 mA, U5 0.17 mA, U3 0.0009 mA, U2 0.0009 mA, U6 0 mA) |
| source_path | 1.31 ohm: FB1 10 mohm; F1 fuse 1.2 ohm max; source and cable 0.1 ohm assumed |
| output_caps_effective | 26.352uF |
| copper | no board: 20 mohm, 5 nH assumed |
| regulator_model | PI loop, 50 kHz crossover (assumed), dropout 0.70 ohm, limit 1300 mA |
| nominal input, this rail only | Vin 4.95 V: +3V3 min 3.297 V, settles 3.299 V; VBUS min 4.917 V |
| minimum input, this rail only | Vin 4.40 V: +3V3 min 3.297 V, settles 3.299 V; VBUS min 4.367 V |

Basis: part model parts/tlv1117lv33.yaml (verified against datasheet): dropout, current limit; simplified ngspice model, see docs/simulation.md. Source resistance and loop bandwidth are assumptions unless set in boardlint.yaml.

### 13 supply rail(s) with a known voltage

`power.rails` · nets: +1V1, +3V3, /RP2350/VREG_AVDD, /vfused, VBUS, VBUSRW · confidence: medium

+1V1 1.067-1.133 V (U6 VREG_FB output); +3V3 3.25-3.349 V (U1 TLV1117LV33 output); /RP2350/VREG_AVDD 3.25-3.349 V (+3V3 through R45 (RC filter)); /vfused 4.4-5.5 V (VBUS through FB1); VBUS 4.4-5.5 V (USB VBUS range (name)); VBUSRW 4.4-5.5 V (USB VBUS range (name)); carrier//VCIN 3.25-3.349 V (+3V3 through carrier/R2); carrier//VDIN 3.25-3.349 V (+3V3 through carrier/R4); carrier/VCCD 1.773-1.827 V (carrier/VCC_{REG} through carrier/R14); carrier/VCC_{REG} 1.773-1.827 V (carrier/U1 AP2112K-1.8 output); carrier/VDDA 3.25-3.349 V (carrier/VDD_{REG} through carrier/R15); carrier/VDD_{IO} 3.25-3.349 V (carrier/VDD_{REG} through carrier/R13); carrier/VDD_{REG} 3.25-3.349 V (carrier//VDIN through carrier/R8)

Basis: regulator models, net names, boardlint.yaml; override with rails: in boardlint.yaml.

### carrier/U1 load on carrier/VCC_{REG} is unknown

`power.regulator` · parts: carrier/U1 · nets: carrier/VCC_{REG} · confidence: high

No part on the rail has a current in its model (no ICs not counted): dropout and thermal checks skipped.

### 61 capacitor(s) on known rails carry no voltage rating in the schematic

`ratings.passives` · confidence: high

Add a Voltage property (or put it in the value, e.g. '10uF 16V') and they will be checked.

### Reset of U6: U6.35(RUN) on /RUN

`reset.circuit` · parts: U6 · nets: /RUN · confidence: high

internal pull-up only; connector J8.2(Pin_2).

| | |
|---|---|
| pull_up | none |
| capacitance | none |
| tau_ms | None |

## Coverage

| Check | Status | |
|---|---|---|
| `mate.geometry` | ran |  |
| `mate.pins` | ran |  |
| `footprint.pin_map (baseboard)` | ran | 1 finding(s), 0.00 s |
| `layout.coupling (baseboard)` | ran | 1 finding(s), 2.28 s |
| `layout.impedance (baseboard)` | ran | 3 finding(s), 0.35 s |
| `layout.ir_drop (baseboard)` | ran | 0 finding(s), 2.27 s |
| `layout.return_path (baseboard)` | ran | 2 finding(s), 1.43 s |
| `layout.track_current (baseboard)` | ran | 0 finding(s), 0.00 s |
| `sync.schematic_board (baseboard)` | ran | 1 finding(s), 0.00 s |
| `bom.value_mpn (baseboard)` | skipped | not selected |
| `clock.source (baseboard)` | skipped | not selected |
| `decoupling.per_part (baseboard)` | ran | 1 finding(s), 0.00 s |
| `decoupling.regulator_caps (baseboard)` | ran | 1 finding(s), 0.00 s |
| `footprint.pin_map (baseboard)` | skipped | not selected |
| `i2c.bus (baseboard)` | skipped | not selected |
| `layout.coupling (baseboard)` | skipped | not selected |
| `layout.impedance (baseboard)` | skipped | not selected |
| `layout.ir_drop (baseboard)` | skipped | not selected |
| `layout.return_path (baseboard)` | skipped | not selected |
| `layout.track_current (baseboard)` | skipped | not selected |
| `led.chain (baseboard)` | skipped | not selected |
| `load.inductive (baseboard)` | skipped | not selected |
| `mcu.alt_function (baseboard)` | skipped | not selected |
| `mcu.pin_use (baseboard)` | skipped | not selected |
| `mcu.strapping (baseboard)` | skipped | not selected |
| `net.name_mismatch (baseboard)` | skipped | not selected |
| `pin.floating_control (baseboard)` | skipped | not selected |
| `pin.name_voltage (baseboard)` | skipped | not selected |
| `pin.requirements (baseboard)` | skipped | not selected |
| `pin.strap_strength (baseboard)` | skipped | not selected |
| `polarity.polarised_parts (baseboard)` | skipped | not selected |
| `power.budget (baseboard)` | skipped | not selected |
| `power.droop (baseboard)` | skipped | not selected |
| `power.logic_level (baseboard)` | skipped | not selected |
| `power.pin_voltage (baseboard)` | skipped | not selected |
| `power.rails (baseboard)` | skipped | not selected |
| `power.regulator (baseboard)` | skipped | not selected |
| `power.source_pin (baseboard)` | skipped | not selected |
| `power.supply_range (baseboard)` | skipped | not selected |
| `power.unpowered (baseboard)` | skipped | not selected |
| `ratings.fets (baseboard)` | skipped | not selected |
| `ratings.passives (baseboard)` | skipped | not selected |
| `reset.circuit (baseboard)` | skipped | not selected |
| `sim.i2c (baseboard)` | skipped | not selected |
| `sim.led_chain (baseboard)` | skipped | not selected |
| `spi.bus (baseboard)` | skipped | not selected |
| `sync.schematic_board (baseboard)` | skipped | not selected |
| `uart.direction (baseboard)` | skipped | not selected |
| `usb.wiring (baseboard)` | skipped | not selected |
| `footprint.pin_map (carrier)` | ran | 0 finding(s), 0.00 s |
| `layout.coupling (carrier)` | ran | 1 finding(s), 0.07 s |
| `layout.impedance (carrier)` | ran | 1 finding(s), 0.01 s |
| `layout.ir_drop (carrier)` | ran | 0 finding(s), 0.98 s |
| `layout.return_path (carrier)` | ran | 0 finding(s), 0.03 s |
| `layout.track_current (carrier)` | ran | 0 finding(s), 0.00 s |
| `sync.schematic_board (carrier)` | ran | 0 finding(s), 0.00 s |
| `bom.value_mpn (carrier)` | skipped | not selected |
| `clock.source (carrier)` | skipped | not selected |
| `decoupling.per_part (carrier)` | ran | 0 finding(s), 0.00 s |
| `decoupling.regulator_caps (carrier)` | ran | 0 finding(s), 0.00 s |
| `footprint.pin_map (carrier)` | skipped | not selected |
| `i2c.bus (carrier)` | skipped | not selected |
| `layout.coupling (carrier)` | skipped | not selected |
| `layout.impedance (carrier)` | skipped | not selected |
| `layout.ir_drop (carrier)` | skipped | not selected |
| `layout.return_path (carrier)` | skipped | not selected |
| `layout.track_current (carrier)` | skipped | not selected |
| `led.chain (carrier)` | skipped | not selected |
| `load.inductive (carrier)` | skipped | not selected |
| `mcu.alt_function (carrier)` | skipped | not selected |
| `mcu.pin_use (carrier)` | skipped | not selected |
| `mcu.strapping (carrier)` | skipped | not selected |
| `net.name_mismatch (carrier)` | skipped | not selected |
| `pin.floating_control (carrier)` | skipped | not selected |
| `pin.name_voltage (carrier)` | skipped | not selected |
| `pin.requirements (carrier)` | skipped | not selected |
| `pin.strap_strength (carrier)` | skipped | not selected |
| `polarity.polarised_parts (carrier)` | skipped | not selected |
| `power.budget (carrier)` | skipped | not selected |
| `power.droop (carrier)` | skipped | not selected |
| `power.logic_level (carrier)` | skipped | not selected |
| `power.pin_voltage (carrier)` | skipped | not selected |
| `power.rails (carrier)` | skipped | not selected |
| `power.regulator (carrier)` | skipped | not selected |
| `power.source_pin (carrier)` | skipped | not selected |
| `power.supply_range (carrier)` | skipped | not selected |
| `power.unpowered (carrier)` | skipped | not selected |
| `ratings.fets (carrier)` | skipped | not selected |
| `ratings.passives (carrier)` | skipped | not selected |
| `reset.circuit (carrier)` | skipped | not selected |
| `sim.i2c (carrier)` | skipped | not selected |
| `sim.led_chain (carrier)` | skipped | not selected |
| `spi.bus (carrier)` | skipped | not selected |
| `sync.schematic_board (carrier)` | skipped | not selected |
| `uart.direction (carrier)` | skipped | not selected |
| `usb.wiring (carrier)` | skipped | not selected |
| `bom.value_mpn` | ran | 1 finding(s), 0.00 s |
| `clock.source` | ran | 1 finding(s), 0.00 s |
| `decoupling.per_part` | skipped | not selected |
| `decoupling.regulator_caps` | skipped | not selected |
| `i2c.bus` | ran | 0 finding(s), 0.00 s |
| `led.chain` | ran | 0 finding(s), 0.00 s |
| `load.inductive` | ran | 0 finding(s), 0.00 s |
| `mcu.alt_function` | ran | 0 finding(s), 0.00 s |
| `mcu.pin_use` | ran | 2 finding(s), 0.00 s |
| `mcu.strapping` | ran | 0 finding(s), 0.00 s |
| `net.name_mismatch` | ran | 0 finding(s), 0.00 s |
| `pin.floating_control` | ran | 0 finding(s), 0.00 s |
| `pin.name_voltage` | ran | 0 finding(s), 0.00 s |
| `pin.requirements` | ran | 0 finding(s), 0.00 s |
| `pin.strap_strength` | ran | 0 finding(s), 0.00 s |
| `polarity.polarised_parts` | ran | 0 finding(s), 0.00 s |
| `power.budget` | ran | 0 finding(s), 0.00 s |
| `power.droop` | ran | 1 finding(s), 1.14 s |
| `power.logic_level` | ran | 2 finding(s), 0.00 s |
| `power.pin_voltage` | ran | 0 finding(s), 0.30 s |
| `power.rails` | ran | 1 finding(s), 0.00 s |
| `power.regulator` | ran | 1 finding(s), 0.00 s |
| `power.source_pin` | ran | 0 finding(s), 0.00 s |
| `power.supply_range` | ran | 0 finding(s), 0.00 s |
| `power.unpowered` | ran | 0 finding(s), 0.00 s |
| `ratings.fets` | ran | 0 finding(s), 0.00 s |
| `ratings.passives` | ran | 1 finding(s), 0.00 s |
| `reset.circuit` | ran | 1 finding(s), 0.00 s |
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
| U2, U3 | NC7SP14P5X | nc7sv14 | yes |
| U4 | 157112V12700 | we-157112v12700 | no |
| U5 | MCP6001-OT | mcp6001 | yes |
| U6 | RP2350-QFN80 | rp2350b | yes |
| U7 | W25Q32JVSS | w25q32jv | yes |
| carrier/J1 | DF12NB-60DS-0.5V_51 | **none: heuristics only** |  |
| carrier/J2 | Conn_01x12 | **none: heuristics only** |  |
| carrier/J3 | DF12NB-50DS-0.5V_51 | **none: heuristics only** |  |
| carrier/U1, carrier/U2 | AP2112K-1.8 | ap2112k-1.8 | yes |
| carrier/U3 | 24LC02 | 24lc02b | yes |
| carrier/U4 | Openframe_QFN_TT06_REV2 | tt-asic-sky130-qfn | no |

## Known issues of the parts used

From errata sheets and forums, recorded in the part models. Not checked against this design.

- **DMG2305UX-7** (lcsc-c5261054-is-not-the-diodes-part): LCSC C5261054 is sold as "DMG2305UX-7" but is made by HXY MOSFET, not Diodes. Its own datasheet gives a +/-12 V gate rating (Diodes +/-8 V), threshold -0.4 to -1.0 V (Diodes -0.5 to -0.9 V), RDS(on) 45 / 60 / 85 mOhm max at -4.5 / -2.5 / -1.8 V (Diodes 52 / 100 / 200), PD 1.31 W and 120 C/W junction to ambient (Diodes 1.4 W, 90 C/W). The genuine Diodes part is LCSC C150470. A circuit that leans on the exact threshold or RDS(on), such as a current source or a linear-region pass element, should be checked against the part that is actually fitted. Source: https://www.lcsc.com/product-detail/C5261054.html and its datasheet https://datasheet.lcsc.com/datasheet/pdf/b91d074ff27bcf2102159ebbd6d79f51.pdf (HXY DMG2305UX-7, 6 pages, p.1-2 read 2026-11-25)
- **TLV1117LV33** (alternate-az1117c-not-equivalent): The alternate AZ1117CH-3.3TRG1 (Diodes AZ1117C) fits the footprint but is a different kind of regulator: it requires at least 10 uF on the output (TLV1117LV: 1 uF), drops 1.3 V max at 0.8 A (TLV1117LV: 0.7 V max at 1 A) so 3.3 V out needs about 4.6 V in, draws 4 mA typ / 6 mA max with no load (TLV1117LV: 0.05 / 0.1 mA) and accepts up to 15 V in (TLV1117LV: 5.5 V, 6 V absolute maximum). Check the output capacitor and the input headroom for whichever part is fitted. Source: Diodes AZ1117C DS36676 Rev. 5 - 2, note 4 p.3, ratings p.4, AZ1117C-3.3 table p.7; TI SBVS160C p.4-5, p.13
- **MCP6001-OT** (sot23-pinout-variants): MCP6001, MCP6001R and MCP6001U have three different SOT-23-5 pinouts (output on pin 1, 1 or 4; VDD on pin 5, 2 or 5). The ordering code (MCP6001T / MCP6001RT / MCP6001UT) has to be the variant the symbol and footprint were drawn for; this file assumes pin 1 VOUT, 2 VSS, 3 VIN+, 4 VIN-, 5 VDD. Source: Microchip DS20001733L, package types p.1 and Table 3-1 p.11
- **AP2112K-1.8** (foldback-start-up): With a current load already on the output before the part is enabled (multiple or negative supplies, a current-source load) the fold-back current limit, 50 mA at VOUT = 0, may prevent start-up. Source: Diodes AP2112 DS39724 Rev. 2 - 2, Application Note p.11
