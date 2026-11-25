# boardlint review: dinolight

**1 error, 16 warnings, 42 notes.** 144 components, 84 nets; netlist from the board.

- schematic and board netlists agree (84 multi-pin nets)

## Errors

### +3V3 sags to 2.05 V under load

`power.droop` · parts: U3, U4 · nets: +3V3, +BATT · confidence: low

U4 (ESP32-S3-MINI-1-N8) needs 3 V. Worst corner: minimum input, everything switching (source at 3.00 V): +3V3 dips to 2.05 V and settles at 2.05 V, with +BATT pulled down to 2.42 V across 0.45 ohm of source path. At nominal input on its own the rail holds 3.07 V.

| | |
|---|---|
| load_step | 95 -> 356 mA in 10 us (U4 355 mA, U7 0.393 mA, U5 0.185 mA, U6 0.03 mA) |
| source_path | 0.45 ohm: Q1 Rds(on) 85 mohm at |Vgs| 2.5 V; SJ1 10 mohm; F1 fuse 0.21 ohm max; cell and its protection circuit 0.15 ohm assumed |
| output_caps_effective | 20.8uF |
| copper | extracted from the routed copper, U3.5(VOUT) to U4.3(3V3): 152 mohm, 90 nH |
| regulator_model | PI loop, 50 kHz crossover (assumed), dropout 0.88 ohm, limit 780 mA |
| other_loads_on_input | 914 mA (D21 43.5 mA, D1 43.5 mA, D2 43.5 mA, D3 43.5 mA, D4 43.5 mA, +17 more) |
| nominal input, this rail only | Vin 3.60 V: +3V3 min 3.070 V, settles 3.070 V; +BATT min 3.438 V |
| minimum input, this rail only | Vin 3.00 V: +3V3 min 2.470 V, settles 2.470 V; +BATT min 2.838 V |
| nominal input, everything switching | Vin 3.60 V: +3V3 min 2.654 V, settles 2.654 V; +BATT min 3.023 V |
| minimum input, everything switching | Vin 3.00 V: +3V3 min 2.054 V, settles 2.054 V; +BATT min 2.423 V |

Basis: part model parts/rt9080-33.yaml (verified against datasheet): dropout, current limit; simplified ngspice model, see docs/simulation.md. Source resistance and loop bandwidth are assumptions unless set in boardlint.yaml.

## Warnings

### U5 supply +3V3: nearest 100nF+ capacitor is 8.4 mm away

`decoupling.per_part` · parts: U5, C34 · nets: +3V3 · confidence: high

U5 (LIS2DH12TR) wants 1 within 6 mm of its supply pin; closest are C34 at 8.4 mm, C33 at 9.7 mm, C4 at 23.8 mm (pad to pad, straight line). Distance adds loop inductance: about 1 nH per mm of trace.

| | |
|---|---|
| required_mm | 6.0 |
| nearest_mm | 8.39 |

Basis: part model parts/lis2dh12.yaml (verified against datasheet): 100 nF ceramic as near as possible to pin 9 (Vdd); distance measured on the board.

### U6 supply +3V3: nearest 100nF+ capacitor is 11.4 mm away

`decoupling.per_part` · parts: U6, C36 · nets: +3V3 · confidence: high

U6 (TLV803SDBZR) wants 1 within 6 mm of its supply pin; closest are C36 at 11.4 mm, C37 at 13.8 mm, C6 at 31.9 mm (pad to pad, straight line). Distance adds loop inductance: about 1 nH per mm of trace.

| | |
|---|---|
| required_mm | 6.0 |
| nearest_mm | 11.37 |

Basis: part model parts/tlv803s.yaml (verified against datasheet): 0.1 uF ceramic close to VDD (good practice; also 'to ensure best stability of the threshold voltage'); distance measured on the board.

### U7 supply +3V3: nearest 100nF+ capacitor is 11.4 mm away

`decoupling.per_part` · parts: U7, C36 · nets: +3V3 · confidence: high

U7 (MPR121QR2) wants 1 within 6 mm of its supply pin; closest are C36 at 11.4 mm, C37 at 19.8 mm, C6 at 38.4 mm (pad to pad, straight line). Distance adds loop inductance: about 1 nH per mm of trace.

| | |
|---|---|
| required_mm | 6.0 |
| nearest_mm | 11.42 |

Basis: part model parts/mpr121.yaml (verified against datasheet): VDD is always decoupled with a 0.1 uF ceramic capacitor to VSS; distance measured on the board.

### USB_DM couples into PAD_SPINE6 (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_SPINE6, USB_DM · confidence: low

USB_DM (USB data) runs 31 mm side by side on one layer, down to 1.44 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.35 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.35 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.349 |
| side_by_side_mm | 30.5 |
| min_gap_mm | 1.44 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 28.7 |
| aggressor | USB_DM: USB data, 3.366 V swing |
| victim | PAD_SPINE6: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### USB_DP couples into PAD_SPINE6 (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_SPINE6, USB_DP · confidence: low

USB_DP (USB data) runs 33 mm side by side on one layer, down to 0.62 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.72 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.72 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.715 |
| side_by_side_mm | 32.6 |
| min_gap_mm | 0.62 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 29.7 |
| aggressor | USB_DP: USB data, 3.366 V swing |
| victim | PAD_SPINE6: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### +3V3: 1 load(s) are not joined to the source by copper

`layout.ir_drop` · parts: U7 · nets: +3V3 · confidence: medium

No copper path on +3V3 from U3 output to U7.20(VDD). Either the connection is unrouted, or it runs through a zone that is saved unfilled.

Basis: copper connectivity in the board file.

### +BATT: 139 mV is lost in the copper on the way to Q2.2(S) (3.9% of the rail)

`layout.ir_drop` · parts: Q2, Q1 · nets: +BATT · confidence: medium

With every load on +BATT at its maximum (1269 mA in all), fed from Q1 (from BAT_RAW). Supply side 139 mV; the ground return is not included. Solved on the routed copper: track resistance, via barrels and pours as a sheet-resistance mesh. Copper at 20 C; thermal-relief spokes are not modelled.

| | |
|---|---|
| source | Q1 (from BAT_RAW) |
| total_load_A | 1.269 |
| worst | Q2.2(S): 139 mV (139 supply + 0 return) |
| next | U3.1(VIN) 6 mV |
| copper | 47 track segments, 2 vias, 0 pour cells |
| ground | no copper path through GND from J2.MP(MountPin) to the loads' ground pads |
| stack_up | assumed |

Basis: resistor-network solve of the net's copper (boardlint/extract.py); loads are model maxima.

### BAT_P1: 1 load(s) are not joined to the source by copper

`layout.ir_drop` · parts: F1 · nets: BAT_P1 · confidence: medium

No copper path on BAT_P1 from connector J2 to F1.1. Either the connection is unrouted, or it runs through a zone that is saved unfilled.

Basis: copper connectivity in the board file.

### GND is in separate pieces: 27 part(s) have no copper return path to their supply

`layout.ir_drop` · parts: D1, D10, D11, D12, D13, D14, D15, D16 · nets: GND · confidence: medium

No copper on GND joins U2.2(V_{SS}) to J1.A1(GND); D1.4(GND) to J2.MP(MountPin); D10.4(GND) to J2.MP(MountPin); D11.4(GND) to J2.MP(MountPin); D12.4(GND) to J2.MP(MountPin); D13.4(GND) to J2.MP(MountPin); D14.4(GND) to J2.MP(MountPin); D15.4(GND) to J2.MP(MountPin).... The supply current of those parts has no return path on the board as drawn: the ground pour is in fragments, or it is saved unfilled. (A pad counts as joined to a pour of its own net within about a millimetre.)

| | |
|---|---|
| pairs_without_a_path | 27 |

Basis: copper connectivity in the board file.

### SPINE_DATA: 51% of its 32 mm has no ground or supply plane on the next layer

`layout.return_path` · nets: SPINE_DATA · confidence: medium

SPINE_DATA (addressable-LED data (800 kHz, nanosecond edges)). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 16 stretch(es) without cover.

| | |
|---|---|
| length_mm | 31.8 |
| uncovered_mm | 16.3 |
| stretches | 16 |

Basis: filled ground and supply zones in the board file, sampled every 0.5 mm along the tracks.

### BAT_P1F: a 0.4 mm segment carries 1269 mA; IPC-2221 gives 1231 mA for a 10 C rise

`layout.track_current` · nets: BAT_P1F · confidence: medium

At (105.4, 46.0) mm on F.Cu. 4.2 mm of the net's track is over its limit with every load at maximum. This is the current that segment actually carries in the solved network, not the net's total.

| | |
|---|---|
| segment | (105.4, 46.0) mm on F.Cu |
| width_mm | 0.4 |
| current_A | 1.269 |
| ipc2221_A | 1.23 |
| length_over_limit_mm | 4.2 |
| net_total_A | 1.269 |

Basis: IPC-2221 formula; segment current from the resistor-network solve; loads are model maxima.

### BAT_RAW: a 0.4 mm segment carries 1269 mA; IPC-2221 gives 1231 mA for a 10 C rise

`layout.track_current` · nets: BAT_RAW · confidence: medium

At (91.5, 50.9) mm on F.Cu. 14.7 mm of the net's track is over its limit with every load at maximum. This is the current that segment actually carries in the solved network, not the net's total.

| | |
|---|---|
| segment | (91.5, 50.9) mm on F.Cu |
| width_mm | 0.4 |
| current_A | 1.269 |
| ipc2221_A | 1.23 |
| length_over_limit_mm | 14.7 |
| net_total_A | 1.269 |

Basis: IPC-2221 formula; segment current from the resistor-network solve; loads are model maxima.

### F1 may carry 1269 mA; its hold current is 1100 mA

`power.budget` · parts: F1 · nets: BAT_P1, BAT_P1F · confidence: medium

F1 (1.1A) feeds BAT_P1F. Sum of the maximum currents of everything behind it: U4 355 mA, D21 43.5 mA, D1 43.5 mA, D2 43.5 mA, D3 43.5 mA, +21 more. This is the all-on worst case; if firmware limits it, record the limit in boardlint.yaml.

| | |
|---|---|
| through_mA_max | 1269 |
| rating_mA | 1100.0 |
| loads | U4 355 mA, D21 43.5 mA, D1 43.5 mA, D2 43.5 mA, D3 43.5 mA, +21 more |

Basis: part model parts/polyfuse-1812-1.1a.yaml (NOT verified against datasheet).

### U3 drops out of regulation when +BATT is below 3.61 V at peak load

`power.regulator` · parts: U3, U4 · nets: +3V3, +BATT · confidence: medium

+BATT spans 3 to 4.2 V. Below 3.61 V with 356 mA drawn the output follows the input down, about 314 mV beneath it. U4 (ESP32-S3-MINI-1-N8) needs 3 V: at peak load that is lost once +BATT is under 3.31 V, well before 3 V. Expect brown-out resets on current peaks with a part-discharged source.

| | |
|---|---|
| load_max_mA | 355.6 |
| load_typ_mA | 95.0 |
| loads | U4 355 mA, U7 0.393 mA, U5 0.185 mA, U6 0.03 mA |
| vin | +BATT 3-4.2 V (U2 charger float voltage; 3.0 V empty cell assumed) |
| dropout | 530 mV at 600 mA, scaled to 314 mV at 356 mA |
| vin_needed | 3.614 |
| brownout_below_vin | 3.31 |

Basis: part model parts/rt9080-33.yaml (verified against datasheet): dropout; load is the sum of model maxima.

### SK6812MINI-E VDD: VLED can fall to 3 V, below the operating minimum of 3.7 V

`power.supply_range` · parts: D21 · nets: VLED · confidence: high

SK6812 reverse-mount addressable RGB LED (3.2 x 2.8 mm class), 12 mA per colour, single-wire 800 kbit/s: out of specification over the bottom part of the rail's range.

| | |
|---|---|
| rail | VLED 3-4.2 V (+BATT through Q2) |
| part | 3.7-5.5 V, abs max 5.5 V |

Basis: part model parts/sk6812mini-e.yaml (verified against datasheet).

### SK6812SIDE-A VDD: VLED can fall to 3 V, below the operating minimum of 3.7 V

`power.supply_range` · parts: D1 · nets: VLED · confidence: high

SK6812 side-emitting addressable RGB LED, 4.0 x 2.0 x 1.6 mm, 12 mA per colour, single-wire 800 kbit/s: out of specification over the bottom part of the rail's range.

| | |
|---|---|
| rail | VLED 3-4.2 V (+BATT through Q2) |
| part | 3.7-5.5 V, abs max 5.5 V |

Basis: part model parts/sk6812-side-a.yaml (verified against datasheet).

## Notes

### U4 supply +3V3: needs 1 x 22uF or more, the rail has 0 (30.4uF in total)

`decoupling.per_part` · parts: U4 · nets: +3V3 · confidence: high

U4 (ESP32-S3-MINI-1-N8) pins U4.3(3V3). Capacitors on +3V3: 3 x 10uF, 4 x 100nF.

Basis: part model parts/esp32-s3-mini-1.yaml (verified against datasheet): C1 22 uF on VDD33 in the peripheral schematic (Figure 9-1).

### I2C bus SDA / SCL address map

`i2c.bus` · parts: U4, U5, U7 · nets: SCL, SDA · confidence: high

0x19 U5 LIS2DH12TR (U5.3(SA0/SDO)=1); 0x5A U7 MPR121QR2 (U7.4(ADDR) on GND)

### I2C net SCL leaves the board with 4.7k already fitted

`i2c.bus` · nets: SCL · confidence: medium

Breakout modules usually carry their own pull-ups (2.2k to 10k each); every one plugged in lowers the total. Budget for the 3 mA limit.

| | |
|---|---|
| pullups | {'R18': '4.7k'} |
| effective | 4.7k |
| rail | +3V3 |
| r_min_3mA | 989R |
| bus_c_est_pF | 95 |
| t_rise_ns | 379 |

### I2C net SDA leaves the board with 4.7k already fitted

`i2c.bus` · nets: SDA · confidence: medium

Breakout modules usually carry their own pull-ups (2.2k to 10k each); every one plugged in lowers the total. Budget for the 3 mA limit.

| | |
|---|---|
| pullups | {'R17': '4.7k'} |
| effective | 4.7k |
| rail | +3V3 |
| r_min_3mA | 989R |
| bus_c_est_pF | 94 |
| t_rise_ns | 374 |

### I2C pull-up on SCL (4.7k) is too weak for 400 kHz once a cable and module are plugged in

`i2c.bus` · parts: R18 · nets: SCL · confidence: medium

Estimated rise time 379 ns with about 95 pF (board alone: 180 ns; 50 pF allowed for the connector): fine at 100 kHz (limit 1000 ns), over the 300 ns limit of fast mode.

| | |
|---|---|
| pullups | {'R18': '4.7k'} |
| effective | 4.7k |
| rail | +3V3 |
| r_min_3mA | 989R |
| bus_c_est_pF | 95 |
| t_rise_ns | 379 |

Basis: I2C specification (UM10204) table 11: tr; bus capacitance is an estimate.

### I2C pull-up on SDA (4.7k) is too weak for 400 kHz once a cable and module are plugged in

`i2c.bus` · parts: R17 · nets: SDA · confidence: medium

Estimated rise time 374 ns with about 94 pF (board alone: 175 ns; 50 pF allowed for the connector): fine at 100 kHz (limit 1000 ns), over the 300 ns limit of fast mode.

| | |
|---|---|
| pullups | {'R17': '4.7k'} |
| effective | 4.7k |
| rail | +3V3 |
| r_min_3mA | 989R |
| bus_c_est_pF | 94 |
| t_rise_ns | 374 |

Basis: I2C specification (UM10204) table 11: tr; bus capacitance is an estimate.

### Net classes used for coupling: 27 aggressor, 28 victim net(s)

`layout.coupling` · confidence: medium

Aggressors: EYE_DATA, EYE_DIN, SPINE_1, SPINE_10, SPINE_11, SPINE_12, SPINE_13, SPINE_14, SPINE_15, SPINE_16, SPINE_17, SPINE_18, SPINE_19, SPINE_2.... Victims: EN, LDO_EN, PAD_FLIP_F, PAD_FLIP_R, PAD_SNOUT, PAD_SPINE1, PAD_SPINE2, PAD_SPINE3, PAD_SPINE4, PAD_SPINE5, PAD_SPINE6, PAD_SPINE7, PAD_SPINE8, PAD_TAIL, RST_OD, T_FLIP_F, T_FLIP_R, T_SNOUT, T_SPINE1, T_SPINE2....

### SPINE_OUT couples into PAD_SPINE8 (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_SPINE8, SPINE_OUT · confidence: low

SPINE_OUT (addressable-LED data (800 kHz, nanosecond edges)) runs 7 mm directly above or below it. A fingertip changes an electrode by around a picofarad or less. 0.19 pF to a line toggling 3.3 V can show up as touch noise or false touches while that line is active. Estimated 0.19 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.191 |
| side_by_side_mm | 0.0 |
| min_gap_mm | None |
| crossing_over_mm | 6.9 |
| of_which_over_ground_mm | 0.0 |
| aggressor | SPINE_OUT: addressable-LED data (800 kHz, nanosecond edges), 3.3 V swing |
| victim | PAD_SPINE8: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### USB_DM couples into PAD_SNOUT (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_SNOUT, USB_DM · confidence: low

USB_DM (USB data) runs 7 mm side by side on one layer, down to 1.27 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.16 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.16 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.157 |
| side_by_side_mm | 7.5 |
| min_gap_mm | 1.27 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 0.0 |
| aggressor | USB_DM: USB data, 3.366 V swing |
| victim | PAD_SNOUT: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### USB_DM couples into PAD_SPINE2 (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_SPINE2, USB_DM · confidence: low

USB_DM (USB data) runs 3 mm side by side on one layer, down to 0.95 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.08 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.08 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.077 |
| side_by_side_mm | 3.0 |
| min_gap_mm | 0.95 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 0.0 |
| aggressor | USB_DM: USB data, 3.366 V swing |
| victim | PAD_SPINE2: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### USB_DP couples into PAD_SNOUT (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_SNOUT, USB_DP · confidence: low

USB_DP (USB data) runs 5 mm side by side on one layer, down to 0.45 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.13 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.13 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.133 |
| side_by_side_mm | 5.0 |
| min_gap_mm | 0.45 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 0.0 |
| aggressor | USB_DP: USB data, 3.366 V swing |
| victim | PAD_SNOUT: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### USB_DP couples into PAD_SPINE4 (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_SPINE4, USB_DP · confidence: low

USB_DP (USB data) runs 25 mm side by side on one layer, down to 1.34 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.30 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.30 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.295 |
| side_by_side_mm | 25.2 |
| min_gap_mm | 1.34 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 25.2 |
| aggressor | USB_DP: USB data, 3.366 V swing |
| victim | PAD_SPINE4: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### Line parameters of 25 fast net(s)

`layout.impedance` · confidence: low

USB_DM: 105 mm, 0.15 mm on F.Cu, 141 ohm, 650 ps, 4.0 pF, 61% over a plane, 5 vias; USB_DP: 96 mm, 0.15 mm on F.Cu, 141 ohm, 598 ps, 3.7 pF, 61% over a plane, 4 vias; SPINE_DATA: 60 mm, 0.15 mm on B.Cu, 141 ohm, 369 ps, 2.3 pF, 62% over a plane, 6 vias; EYE_DATA: 33 mm, 0.15 mm on F.Cu, 141 ohm, 225 ps, 1.2 pF, 6% over a plane, 4 vias; SPINE_OUT: 13 mm, 0.15 mm on F.Cu, 141 ohm, 90 ps, 0.5 pF, 15% over a plane, 0 vias; SPINE_17: 10 mm, 0.2 mm on F.Cu, 134 ohm, 58 ps, 0.4 pF, 100% over a plane, 0 vias; SPINE_12: 10 mm, 0.2 mm on F.Cu, 134 ohm, 58 ps, 0.4 pF, 100% over a plane, 0 vias; SPINE_11: 10 mm, 0.2 mm on F.Cu, 134 ohm, 58 ps, 0.4 pF, 100% over a plane, 0 vias; SPINE_10: 10 mm, 0.2 mm on F.Cu, 134 ohm, 58 ps, 0.4 pF, 100% over a plane, 0 vias; SPINE_9: 10 mm, 0.2 mm on F.Cu, 134 ohm, 57 ps, 0.4 pF, 100% over a plane, 0 vias....

| | |
|---|---|
| stack_up | assumed: F.Cu / 1.53 mm er 4.5 / B.Cu |

Basis: microstrip / stripline formulas on the stack-up.

### SPINE_DATA is electrically long: 56 mm end to end, 349 ps one way

`layout.impedance` · parts: U4 · nets: SPINE_DATA, SPINE_DIN · confidence: low

addressable-LED data (800 kHz, nanosecond edges). 56 mm between its furthest pads (60 mm routed in all). For a 2 ns edge a trace acts as a transmission line beyond about 54 mm (delay over one sixth of the rise time). It has R14 (330R) in series, which damps the reflection. Line impedance about 141 ohm.

| | |
|---|---|
| end_to_end_mm | 56.4 |
| routed_mm | 59.6 |
| delay_ps | 349 |
| z0 | 141 |
| assumed_rise_ns | 2.0 |
| stack_up | assumed |

Basis: microstrip / stripline formulas on the stack-up; rise time is an assumption (signals: rise_ns in boardlint.yaml).

### USB pair: about 193 ohm differential, 8.5 mm length mismatch

`layout.impedance` · nets: USB_DM, USB_DP · confidence: low

D+ 96 mm, D- 105 mm (mismatch 8.5 mm). Routed as a pair for 43 mm at a 0.67 mm gap: about 193 ohm differential; USB asks for 90 ohm +/- 15 %. At full speed (12 Mbit/s) this is tolerant; at high speed (480 Mbit/s) both the impedance and a mismatch over about 1 mm matter.

| | |
|---|---|
| d_plus_mm | 96.2 |
| d_minus_mm | 104.7 |
| mismatch_mm | 8.5 |
| routed_as_a_pair_mm | 43.3 |
| stack_up | assumed |
| gap_mm | 0.67 |
| z_diff | 193 |

Basis: edge-coupled microstrip formula on the stack-up.

### +3V3: 54 mV is lost in the copper on the way to U4.3(3V3) (1.6% of the rail)

`layout.ir_drop` · parts: U4, U3 · nets: +3V3 · confidence: medium

With every load on +3V3 at its maximum (356 mA in all), fed from U3 output. Supply side 54 mV; the ground return is not included. Solved on the routed copper: track resistance, via barrels and pours as a sheet-resistance mesh. Copper at 20 C; thermal-relief spokes are not modelled.

| | |
|---|---|
| source | U3 output |
| total_load_A | 0.356 |
| worst | U4.3(3V3): 54 mV (54 supply + 0 return) |
| next | U6.3(VDD) 40 mV; U5.9(Vdd) 11 mV; U5.10(Vdd_IO) 11 mV |
| copper | 75 track segments, 8 vias, 0 pour cells |
| ground | no copper path through GND from U3.2(GND) to the loads' ground pads |
| stack_up | assumed |

Basis: resistor-network solve of the net's copper (boardlint/extract.py); loads are model maxima.

### BAT_P1F: 7 mV is lost in the copper on the way to SJ1.2(C) (0.2% of the rail)

`layout.ir_drop` · parts: SJ1, F1 · nets: BAT_P1F · confidence: medium

With every load on BAT_P1F at its maximum (1269 mA in all), fed from F1 (from BAT_P1). Supply side 7 mV; the ground return is not included. Solved on the routed copper: track resistance, via barrels and pours as a sheet-resistance mesh. Copper at 20 C; thermal-relief spokes are not modelled.

| | |
|---|---|
| source | F1 (from BAT_P1) |
| total_load_A | 1.269 |
| worst | SJ1.2(C): 7 mV (7 supply + 0 return) |
| next | none |
| copper | 3 track segments, 0 vias, 0 pour cells |
| ground | ground return not included (the loads here have no ground pad of their own) |
| stack_up | assumed |

Basis: resistor-network solve of the net's copper (boardlint/extract.py); loads are model maxima.

### BAT_RAW: 24 mV is lost in the copper on the way to Q1.3(D) (0.7% of the rail)

`layout.ir_drop` · parts: Q1, SJ1 · nets: BAT_RAW · confidence: medium

With every load on BAT_RAW at its maximum (1269 mA in all), fed from SJ1 (from BAT_P1F). Supply side 24 mV; the ground return is not included. Solved on the routed copper: track resistance, via barrels and pours as a sheet-resistance mesh. Copper at 20 C; thermal-relief spokes are not modelled.

| | |
|---|---|
| source | SJ1 (from BAT_P1F) |
| total_load_A | 1.269 |
| worst | Q1.3(D): 24 mV (24 supply + 0 return) |
| next | none |
| copper | 7 track segments, 0 vias, 0 pour cells |
| ground | ground return not included (the loads here have no ground pad of their own) |
| stack_up | assumed |

Basis: resistor-network solve of the net's copper (boardlint/extract.py); loads are model maxima.

### VLED: 79 mV is lost in the copper on the way to D20.2(VDD) (2.2% of the rail)

`layout.ir_drop` · parts: D20, Q2 · nets: VLED · confidence: medium

With every load on VLED at its maximum (914 mA in all), fed from Q2 (from +BATT). Supply side 79 mV; the ground return is not included. Solved on the routed copper: track resistance, via barrels and pours as a sheet-resistance mesh. Copper at 20 C; thermal-relief spokes are not modelled.

| | |
|---|---|
| source | Q2 (from +BATT) |
| total_load_A | 0.913 |
| worst | D20.2(VDD): 79 mV (79 supply + 0 return) |
| next | D19.2(VDD) 78 mV; D18.2(VDD) 78 mV; D17.2(VDD) 77 mV |
| copper | 156 track segments, 0 vias, 0 pour cells |
| ground | no copper path through GND from J2.MP(MountPin) to the loads' ground pads |
| stack_up | assumed |

Basis: resistor-network solve of the net's copper (boardlint/extract.py); loads are model maxima.

### EYE_DATA: 72% of its 26 mm has no ground or supply plane on the next layer

`layout.return_path` · nets: EYE_DATA · confidence: medium

EYE_DATA (addressable-LED data (800 kHz, nanosecond edges)). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 10 stretch(es) without cover.

| | |
|---|---|
| length_mm | 25.6 |
| uncovered_mm | 18.3 |
| stretches | 10 |

Basis: filled ground and supply zones in the board file, sampled every 0.5 mm along the tracks.

### SPINE_DIN: 49% of its 28 mm has no ground or supply plane on the next layer

`layout.return_path` · nets: SPINE_DIN · confidence: medium

SPINE_DIN (addressable-LED data (800 kHz, nanosecond edges)). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 9 stretch(es) without cover.

| | |
|---|---|
| length_mm | 27.7 |
| uncovered_mm | 13.6 |
| stretches | 9 |

Basis: filled ground and supply zones in the board file, sampled every 0.5 mm along the tracks.

### SPINE_OUT: 70% of its 13 mm has no ground or supply plane on the next layer

`layout.return_path` · nets: SPINE_OUT · confidence: medium

SPINE_OUT (addressable-LED data (800 kHz, nanosecond edges)). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 2 stretch(es) without cover.

| | |
|---|---|
| length_mm | 13.4 |
| uncovered_mm | 9.4 |
| stretches | 2 |

Basis: filled ground and supply zones in the board file, sampled every 0.5 mm along the tracks.

### USB_DM: 40% of its 105 mm has no ground or supply plane on the next layer

`layout.return_path` · nets: USB_DM · confidence: medium

USB_DM (USB data). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 26 stretch(es) without cover.

| | |
|---|---|
| length_mm | 104.7 |
| uncovered_mm | 41.9 |
| stretches | 26 |

Basis: filled ground and supply zones in the board file, sampled every 0.5 mm along the tracks.

### USB_DP: 36% of its 96 mm has no ground or supply plane on the next layer

`layout.return_path` · nets: USB_DP · confidence: medium

USB_DP (USB data). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 23 stretch(es) without cover.

| | |
|---|---|
| length_mm | 96.2 |
| uncovered_mm | 34.7 |
| stretches | 23 |

Basis: filled ground and supply zones in the board file, sampled every 0.5 mm along the tracks.

### +BATT: a 0.4 mm segment carries 914 mA; IPC-2221 gives 1231 mA for a 10 C rise

`layout.track_current` · nets: +BATT · confidence: medium

At (91.9, 55.9) mm on F.Cu. 0.0 mm of the net's track is over its limit with every load at maximum. This is the current that segment actually carries in the solved network, not the net's total.

| | |
|---|---|
| segment | (91.9, 55.9) mm on F.Cu |
| width_mm | 0.4 |
| current_A | 0.914 |
| ipc2221_A | 1.23 |
| length_over_limit_mm | 0.0 |
| net_total_A | 1.269 |

Basis: IPC-2221 formula; segment current from the resistor-network solve; loads are model maxima.

### VLED: a 0.4 mm segment carries 914 mA; IPC-2221 gives 1231 mA for a 10 C rise

`layout.track_current` · nets: VLED · confidence: medium

At (196.5, 55.4) mm on F.Cu. 0.0 mm of the net's track is over its limit with every load at maximum. This is the current that segment actually carries in the solved network, not the net's total.

| | |
|---|---|
| segment | (196.5, 55.4) mm on F.Cu |
| width_mm | 0.4 |
| current_A | 0.914 |
| ipc2221_A | 1.23 |
| length_over_limit_mm | 0.0 |
| net_total_A | 0.913 |

Basis: IPC-2221 formula; segment current from the resistor-network solve; loads are model maxima.

### LED chain on EYE_DATA

`led.chain` · parts: D21, U4 · nets: EYE_DATA, EYE_DIN · confidence: high

1 LED(s): D21; driven by U4.30(IO48) through R15 (330R).

### LED chain on SPINE_DATA

`led.chain` · parts: D1, U4 · nets: SPINE_DATA, SPINE_DIN · confidence: high

20 LED(s): D1, D2, ... D20; driven by U4.27(IO47) through R14 (330R).

### U4.27(IO47) to D1 DIN: logic high is met in practice, not by the datasheet numbers

`led.chain` · parts: U4, D1 · nets: SPINE_DATA, SPINE_DIN · confidence: high

The LED input threshold rises to 2.73 V when VLED is at 4.2 V. The driver's guaranteed output high is 2.59 V, but that figure is at its rated load current; into a CMOS input it sits near 3.13 V.

| | |
|---|---|
| driver_rail | +3V3 3.234-3.366 V |
| driver_voh_min | 2.59 |
| led_rail | VLED 3-4.2 V |
| led_vih | 1.95-2.73 V (0.65 x VDD) |

Basis: part model parts/sk6812-side-a.yaml (verified against datasheet): VIH.

### U4.30(IO48) to D21 DIN: logic high is met in practice, not by the datasheet numbers

`led.chain` · parts: U4, D21 · nets: EYE_DATA, EYE_DIN · confidence: high

The LED input threshold rises to 2.73 V when VLED is at 4.2 V. The driver's guaranteed output high is 2.59 V, but that figure is at its rated load current; into a CMOS input it sits near 3.13 V.

| | |
|---|---|
| driver_rail | +3V3 3.234-3.366 V |
| driver_voh_min | 2.59 |
| led_rail | VLED 3-4.2 V |
| led_vih | 1.95-2.73 V (0.65 x VDD) |

Basis: part model parts/sk6812mini-e.yaml (verified against datasheet): VIH.

### U4 pin use: 18 pins in use

`mcu.pin_use` · parts: U4 · confidence: medium

IO0 = BOOT: button [ok; strapping pin]; IO1 = TOUCH_IRQ: interrupt in (U7) [ok: can wake from deep sleep]; IO3 = IO3: test point only [ok; strapping pin]; IO10 = VBAT_SENSE: analog in (+BATT through R6/R7) [ok: ADC1]; IO15 = ACC_INT1: interrupt in (U5) [ok: can wake from deep sleep]; IO16 = ACC_INT2: interrupt in (U5) [ok: can wake from deep sleep]; IO17 = CHG_STAT: digital in (divided from CHG_STAT_5V) [ok]; IO18 = VBUS_DET: digital in (divided from VBUS) [ok]; USB_D- = USB_DM: USB D- (J1) [ok]; USB_D+ = USB_DP: USB D+ (J1) [ok]; IO21 = LED_EN: digital out (to FET gate) [ok]; IO47 = SPINE_DATA: addressable-LED data out (D1) [ok]; IO48 = EYE_DATA: addressable-LED data out (D21) [ok]; IO41 = SDA: I2C SDA (U7) [ok]; IO42 = SCL: I2C SCL (U7) [ok]; TXD0 = UART_TX: test point only [ok]; RXD0 = UART_RX: test point only [ok]; EN = EN: button [ok]

| | |
|---|---|
| IO0 | BOOT: button [ok; strapping pin] |
| IO1 | TOUCH_IRQ: interrupt in (U7) [ok: can wake from deep sleep] |
| IO3 | IO3: test point only [ok; strapping pin] |
| IO10 | VBAT_SENSE: analog in (+BATT through R6/R7) [ok: ADC1] |
| IO15 | ACC_INT1: interrupt in (U5) [ok: can wake from deep sleep] |
| IO16 | ACC_INT2: interrupt in (U5) [ok: can wake from deep sleep] |
| IO17 | CHG_STAT: digital in (divided from CHG_STAT_5V) [ok] |
| IO18 | VBUS_DET: digital in (divided from VBUS) [ok] |
| USB_D- | USB_DM: USB D- (J1) [ok] |
| USB_D+ | USB_DP: USB D+ (J1) [ok] |
| IO21 | LED_EN: digital out (to FET gate) [ok] |
| IO47 | SPINE_DATA: addressable-LED data out (D1) [ok] |
| IO48 | EYE_DATA: addressable-LED data out (D21) [ok] |
| IO41 | SDA: I2C SDA (U7) [ok] |
| IO42 | SCL: I2C SCL (U7) [ok] |
| TXD0 | UART_TX: test point only [ok] |
| RXD0 | UART_RX: test point only [ok] |
| EN | EN: button [ok] |

Basis: part model parts/esp32-s3-mini-1.yaml (verified against datasheet): pin capabilities; use inferred from what else is on each net.

### Strapping pin U4.4(IO0) is used (BOOT)

`mcu.strapping` · parts: U4, SW3 · nets: BOOT · confidence: medium

U4 (ESP32-S3-MINI-1-N8) samples this pin at reset (default: high; boot_high: SPI boot: normal boot from flash (IO46 any value); boot_low: joint download boot (UART0 / USB), needs IO46 low). Connected here: SW3.1. Whatever is attached must not hold the wrong level while the module comes out of reset.

Basis: part model parts/esp32-s3-mini-1.yaml (verified against datasheet).

### U4.7(IO3) must not float

`pin.requirements` · parts: U4 · nets: IO3 · confidence: high

U4 (ESP32-S3-MINI-1-N8): only TP8.1 on the net. GPIO3 has no internal pull; its strapping value must be controlled by an external circuit that cannot be high impedance (section 4.4). Applies when: only if EFUSE_STRAP_JTAG_SEL has been burnt to 1; with the default eFuses GPIO3 is ignored (Table 4-5).

Basis: part model parts/esp32-s3-mini-1.yaml (verified against datasheet).

### U2 charge current is 213 mA

`power.budget` · parts: U2, R3 · confidence: high

R3 (4.7k) on U2.5(PROG). Check it against the cell (0.5 C is typical) and against what the USB source may supply.

Basis: part model parts/mcp73831.yaml (verified against datasheet): charge-current formula.

### U4.21(IO17) can see 3.667 V; its limit is 3.53 V

`power.pin_voltage` · parts: U4 · nets: CHG_STAT · confidence: high

Net CHG_STAT (divider R10/R19 from CHG_STAT_5V (U2.1(STAT) high = VBUS)). Limit: supply (+3V3 at its minimum 3.234 V) + 0.3 V. The excess is within a few hundred millivolts: it arises when the two supplies are at opposite ends of their ranges. The source impedance (100k) limits the current into the pin's protection diode to about 20 uA: outside the datasheet limit, harmless in practice. Also note the pin is driven while the part is unpowered if this source comes up first.

| | |
|---|---|
| net_vmax | 3.667 |
| pin_limit | 3.534 |

Basis: part model parts/esp32-s3-mini-1.yaml (verified against datasheet).

### U4.22(IO18) can see 3.667 V; its limit is 3.53 V

`power.pin_voltage` · parts: U4 · nets: VBUS_DET · confidence: high

Net VBUS_DET (divider R8/R9 from VBUS (USB VBUS range (name))). Limit: supply (+3V3 at its minimum 3.234 V) + 0.3 V. The excess is within a few hundred millivolts: it arises when the two supplies are at opposite ends of their ranges. The source impedance (100k) limits the current into the pin's protection diode to about 20 uA: outside the datasheet limit, harmless in practice. Also note the pin is driven while the part is unpowered if this source comes up first.

| | |
|---|---|
| net_vmax | 3.667 |
| pin_limit | 3.534 |

Basis: part model parts/esp32-s3-mini-1.yaml (verified against datasheet).

### 8 supply rail(s) with a known voltage

`power.rails` · nets: +3V3, +BATT, BAT_P1, BAT_P1F, BAT_RAW, EN_USB · confidence: medium

+3V3 3.234-3.366 V (U3 RT9080-33GJ5 output); +BATT 3-4.2 V (U2 charger float voltage; 3.0 V empty cell assumed); BAT_P1 3-4.2 V (BAT_P1F through F1); BAT_P1F 3-4.2 V (BAT_RAW through SJ1); BAT_RAW 3-4.2 V (+BATT through Q1); EN_USB 3.7-5.3 V (VBUS through D23); VBUS 4.4-5.5 V (USB VBUS range (name)); VLED 3-4.2 V (+BATT through Q2)

Basis: regulator models, net names, boardlint.yaml; override with rails: in boardlint.yaml.

### Q3 is driven with 3.23 V; Rds(on) is only specified down to 5 V

`ratings.fets` · parts: Q3 · confidence: medium

Q3 (2N7002): gate driven by U4.25(IO21) from +3V3 (3.234-3.366 V). Below the lowest specified gate voltage the on-resistance is not guaranteed (it only switches a pull-up here, so it hardly matters).

| | |
|---|---|
| vgs_on_min | 3.23 |
| rds_on_specified_at_V | [5.0, 10.0] |
| vgs_th_max | 2.5 |

Basis: part model parts/2n7002.yaml (verified against datasheet).

### 34 capacitor(s) on known rails carry no voltage rating in the schematic

`ratings.passives` · confidence: high

Add a Voltage property (or put it in the value, e.g. '10uF 16V') and they will be checked.

### Reset of U4: U4.45(EN) on EN

`reset.circuit` · parts: U4 · nets: EN, RST_OD · confidence: high

pull-up 100k (R16); 100nF to ground, time constant 10 ms; open-drain U6.2(~{RESET}); button SW2.1; through R32 (1k).

| | |
|---|---|
| pull_up | 100k |
| capacitance | 100nF |
| tau_ms | 10.0 |

### I2C bus SDA / SCL: 2 of 2 modelled target(s) answer in simulation

`sim.i2c` · parts: U5, U7 · nets: SCL, SDA · confidence: high

U5 at 0x19 (register 0x0F = 0x33); U7 at 0x5A (register 0x5C = 0x10). Full address scan found 2 responder(s).

Basis: behavioural Verilog models (boardlint/sim/verilog/i2c_target.v) wired from the netlist; ID registers from the part models.

### 21 of 21 addressable LED(s) latch data in simulation

`sim.led_chain` · parts: D1, D21 · confidence: high

Position along each data line, as simulated: from D1: D1, D2, ... D20; from D21: D21.

Basis: behavioural Verilog model (boardlint/sim/verilog/serial_led.v) wired from the netlist.

## Coverage

| Check | Status | |
|---|---|---|
| `clock.source` | ran | 0 finding(s), 0.00 s |
| `decoupling.per_part` | ran | 4 finding(s), 0.00 s |
| `decoupling.regulator_caps` | ran | 0 finding(s), 0.00 s |
| `footprint.pin_map` | ran | 0 finding(s), 0.00 s |
| `i2c.bus` | ran | 5 finding(s), 0.05 s |
| `layout.coupling` | ran | 8 finding(s), 0.78 s |
| `layout.impedance` | ran | 3 finding(s), 0.11 s |
| `layout.ir_drop` | ran | 8 finding(s), 0.27 s |
| `layout.return_path` | ran | 6 finding(s), 0.37 s |
| `layout.track_current` | ran | 4 finding(s), 0.00 s |
| `led.chain` | ran | 4 finding(s), 0.00 s |
| `load.inductive` | ran | 0 finding(s), 0.00 s |
| `mcu.alt_function` | ran | 0 finding(s), 0.00 s |
| `mcu.pin_use` | ran | 1 finding(s), 0.00 s |
| `mcu.strapping` | ran | 1 finding(s), 0.00 s |
| `net.name_mismatch` | ran | 0 finding(s), 0.00 s |
| `pin.floating_control` | ran | 0 finding(s), 0.00 s |
| `pin.name_voltage` | ran | 0 finding(s), 0.00 s |
| `pin.requirements` | ran | 1 finding(s), 0.00 s |
| `pin.strap_strength` | ran | 0 finding(s), 0.00 s |
| `polarity.polarised_parts` | ran | 0 finding(s), 0.00 s |
| `power.budget` | ran | 2 finding(s), 0.00 s |
| `power.droop` | ran | 1 finding(s), 1.03 s |
| `power.logic_level` | ran | 0 finding(s), 0.00 s |
| `power.pin_voltage` | ran | 2 finding(s), 0.01 s |
| `power.rails` | ran | 1 finding(s), 0.00 s |
| `power.regulator` | ran | 1 finding(s), 0.00 s |
| `power.source_pin` | ran | 0 finding(s), 0.00 s |
| `power.supply_range` | ran | 2 finding(s), 0.00 s |
| `ratings.fets` | ran | 1 finding(s), 0.00 s |
| `ratings.passives` | ran | 1 finding(s), 0.00 s |
| `reset.circuit` | ran | 1 finding(s), 0.00 s |
| `sim.i2c` | ran | 1 finding(s), 0.03 s |
| `sim.led_chain` | ran | 1 finding(s), 0.05 s |
| `spi.bus` | ran | 0 finding(s), 0.00 s |
| `sync.schematic_board` | ran | 0 finding(s), 0.00 s |
| `uart.direction` | ran | 0 finding(s), 0.00 s |
| `usb.wiring` | ran | 0 finding(s), 0.00 s |

## Part models

| Parts | Value | Model | Verified against datasheet |
|---|---|---|---|
| D1, D10, D11, D12 +16 | SK6812SIDE-A | sk6812-side-a | yes |
| D21 | SK6812MINI-E | sk6812mini-e | yes |
| D23 | 1N4148W | 1n4148w | no |
| F1 | 1.1A | polyfuse-1812-1.1a | no |
| J1 | USB-C | usb-c-hro-type-c-31-m-12 | yes |
| J2 | LiPo JST-PH | **none: heuristics only** |  |
| J3 | Qwiic | **none: heuristics only** |  |
| Q1, Q2 | AO3401A | ao3401a | yes |
| Q3 | 2N7002 | 2n7002 | yes |
| SW1 | MSK12C02 | msk12c02 | yes |
| SW2 | RESET | ts-1187a | yes |
| SW3 | BOOT | ts-1187a | yes |
| U1 | USBLC6-2SC6 | usblc6-2 | yes |
| U2 | MCP73831T-2ACI/OT | mcp73831 | yes |
| U3 | RT9080-33GJ5 | rt9080-33 | yes |
| U4 | ESP32-S3-MINI-1-N8 | esp32-s3-mini-1 | yes |
| U5 | LIS2DH12TR | lis2dh12 | yes |
| U6 | TLV803SDBZR | tlv803s | yes |
| U7 | MPR121QR2 | mpr121 | yes |

## Known issues of the parts used

From errata sheets and forums, recorded in the part models. Not checked against this design.

- **SK6812SIDE-A** (3v3-data-with-5v-supply): VIH is 0.65 x VDD, 3.25 V at a 5 V supply (3.58 V at 5.5 V): a 3.3 V MCU output (guaranteed high level typically 0.8 x 3.3 V = 2.64 V) does not meet it, so the first LED's DIN needs a level shifter or a lower LED supply (VDD of 4.0 V or less for 2.64 V). Source: datasheets/C5378721.pdf IC electrical parameters p.6; https://learn.adafruit.com/neopixel-levelshifter/shifting-levels
- **SK6812MINI-E** (3v3-data-with-5v-supply): VIH is 0.65 x VDD, 3.25 V at a 5 V supply (3.58 V at 5.5 V): a 3.3 V MCU output (guaranteed high level typically 0.8 x 3.3 V = 2.64 V) does not meet it, so the first LED's DIN needs a level shifter or a lower LED supply (VDD of 4.0 V or less for 2.64 V). Source: datasheets/C5149201.pdf IC electrical parameters p.6; https://learn.adafruit.com/neopixel-levelshifter/shifting-levels
- **ESP32-S3-MINI-1-N8** (usb-pins-glitch-at-power-up): GPIO19/GPIO20 (USB D-/D+) are not quiet at power-up: Espressif documents high-level glitches of about 60 us on both and D+ toggling until the USB pull-up settles, so anything else wired to these pins sees pulses at power-up and reset. Source: https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html ; forum report of GPIO20 held high about 170 ms during boot: https://esp32.com/viewtopic.php?t=36423
- **ESP32-S3-MINI-1-N8** (strap-io0-low-io46-high-invalid): IO46 high together with IO0 low at reset is not a defined boot mode (the ESP32-S3 Series Datasheet calls the combination invalid); do not pull IO46 up. Source: https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf (section Boot Configurations); module datasheet Table 4-3
- **ESP32-S3-MINI-1-N8** (strap-io45-high-selects-1v8-flash-supply): IO45 high at reset switches VDD_SPI, the supply of the in-package flash, from 3.3 V to the 1.8 V regulator; keep IO45 low or floating during reset unless that is intended. Source: datasheets/ESP32-S3-MINI-1_en.pdf Table 4-4, p.15
- **LIS2DH12TR** (sa0-low-pullup-current): Tying SA0 to GND (address 0x18) draws Vdd_IO / R through the internal SDO/SA0 pull-up (20.4 k at 3.6 V, 30.4 k at 2.5 V typ), about 0.1 mA or more at 3.3 V, many times the sensor's own current, until firmware writes 90h to CTRL_REG0 (1Eh). Source: datasheets/C110926.pdf Table 3 p.9 and CTRL_REG0 p.33; ST community: https://community.st.com/mems-sensors-48/lis2dh12-excessive-current-draw-72791
- **MPR121QR2** (early-datasheet-wrong-address): Rev 0 (9/2009) of the datasheet and of AN3895 gave a wrong I2C address; the address with ADDR at VSS is 0x5A (as in Rev 4), so do not rely on copies of the old revision. Source: https://community.nxp.com/thread/62485
- **MPR121QR2** (read-needs-repeated-start): Register reads need a repeated START between the register-address write and the read; a STOP in between has been reported to make every register read back as zero. Source: https://community.nxp.com/t5/Sensors/MPR121-all-registers-read-zero/m-p/228651 ; datasheet read format p.22
