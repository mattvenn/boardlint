# boardlint review: dinolight

**1 error, 18 warnings, 30 notes.** 160 components, 88 nets; netlist from the schematic.

- schematic and board netlists differ in 7 net group(s); the schematic's is used

## Errors

### +3V3 sags to 2.07 V under load

`power.droop` · parts: U3, U4 · nets: +3V3, +BATT · confidence: low

U4 (ESP32-S3-MINI-1-N8) needs 3 V. Worst corner: minimum input, everything switching (source at 3.00 V): +3V3 dips to 2.07 V and settles at 2.07 V, with +BATT pulled down to 2.46 V across 0.45 ohm of source path. At nominal input on its own the rail holds 3.05 V.

| | |
|---|---|
| load_step | 95 -> 359 mA in 10 us (U4 355 mA, U8 2.2 mA, U9 0.5 mA, U7 0.393 mA, U11 0.26 mA, +3 more) |
| source_path | 0.45 ohm: Q1 Rds(on) 85 mohm at |Vgs| 2.5 V; SJ1 10 mohm; F1 fuse 0.21 ohm max; cell and its protection circuit 0.15 ohm assumed |
| output_caps_effective | 15uF |
| copper | 147 mm (pad to pad x 1.4) of 0.37 mm track: 196 mohm, 209 nH |
| regulator_model | PI loop, 50 kHz crossover (assumed), dropout 0.88 ohm, limit 780 mA |
| other_loads_on_input | 826 mA (D21 43.5 mA, D1 43.5 mA, D2 43.5 mA, D3 43.5 mA, D4 43.5 mA, +15 more) |
| nominal input, this rail only | Vin 3.60 V: +3V3 min 3.050 V, settles 3.050 V; +BATT min 3.437 V |
| minimum input, this rail only | Vin 3.00 V: +3V3 min 2.450 V, settles 2.450 V; +BATT min 2.837 V |
| nominal input, everything switching | Vin 3.60 V: +3V3 min 2.674 V, settles 2.674 V; +BATT min 3.061 V |
| minimum input, everything switching | Vin 3.00 V: +3V3 min 2.074 V, settles 2.074 V; +BATT min 2.461 V |

Basis: part model parts/rt9080-33.yaml (verified against datasheet): dropout, current limit; simplified ngspice model, see docs/simulation.md. Source resistance and loop bandwidth are assumptions unless set in boardlint.yaml.

## Warnings

### D21 supply VLED: nearest 100nF+ capacitor is 7.5 mm away

`decoupling.per_part` · parts: D21, C31 · nets: VLED · confidence: high

D21 (SK6812MINI-012) wants 1 within 6 mm of its supply pin; closest are C31 at 7.5 mm, C11 at 14.9 mm, C12 at 22.3 mm (pad to pad, straight line). Distance adds loop inductance: about 1 nH per mm of trace.

| | |
|---|---|
| required_mm | 6.0 |
| nearest_mm | 7.53 |

Basis: part model parts/sk6812mini-012.yaml (verified against datasheet): one decoupling capacitor per LED between VDD and GND is 'essential' (section 14); the datasheet prints no value; distance measured on the board.

### U4 supply +3V3: needs 1 x 22uF or more, the rail has 0 (21.9uF in total)

`decoupling.per_part` · parts: U4 · nets: +3V3 · confidence: high

U4 (ESP32-S3-MINI-1-N8) pins U4.3(3V3). Capacitors on +3V3: 2 x 10uF, 9 x 100nF, 1 x 1uF.

Basis: part model parts/esp32-s3-mini-1.yaml (verified against datasheet): C1 22 uF on VDD33 in the peripheral schematic (Figure 9-1).

### BZ1: footprint pad(s) 3 have no pin on the symbol

`footprint.pin_map` · parts: BZ1 · confidence: medium

BZ1 (MLT-5020), symbol Device:Buzzer, footprint DinoLight:Buzzer_MLT-5020. They are unconnected on the board. Fine for mounting tabs; a mistake if the part has a function there (exposed pad, second row).

Basis: pin numbers in the schematic symbol against pad numbers in the board file.

### SCL couples into PAD_FLIP_F (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_FLIP_F, SCL · confidence: low

SCL (clock) runs 19 mm side by side on one layer, down to 0.45 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.42 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.42 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.418 |
| side_by_side_mm | 18.9 |
| min_gap_mm | 0.45 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 0.7 |
| aggressor | SCL: clock, 3.366 V swing |
| victim | PAD_FLIP_F: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### SCL couples into PAD_FLIP_R (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_FLIP_R, SCL · confidence: low

SCL (clock) runs 16 mm side by side on one layer, down to 0.21 mm apart and 5 mm directly above or below it. A fingertip changes an electrode by around a picofarad or less. 0.54 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.54 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.54 |
| side_by_side_mm | 15.9 |
| min_gap_mm | 0.21 |
| crossing_over_mm | 4.8 |
| of_which_over_ground_mm | 1.1 |
| aggressor | SCL: clock, 3.366 V swing |
| victim | PAD_FLIP_R: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### SCL couples into PAD_SNOUT (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_SNOUT, SCL · confidence: low

SCL (clock) runs 19 mm side by side on one layer, down to 0.61 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.47 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.47 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.47 |
| side_by_side_mm | 18.6 |
| min_gap_mm | 0.61 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 0.0 |
| aggressor | SCL: clock, 3.366 V swing |
| victim | PAD_SNOUT: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### EYE_DIN: 92% of its 55 mm has no ground copper on the other layer

`layout.return_path` · nets: EYE_DIN · confidence: medium

EYE_DIN (addressable-LED data (800 kHz, nanosecond edges)). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 34 stretch(es) without cover.

| | |
|---|---|
| length_mm | 54.6 |
| uncovered_mm | 50.2 |
| stretches | 34 |

Basis: filled ground zones in the board file, sampled every 0.5 mm along the tracks.

### SCL: 64% of its 288 mm has no ground copper on the other layer

`layout.return_path` · nets: SCL · confidence: medium

SCL (clock). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 111 stretch(es) without cover.

| | |
|---|---|
| length_mm | 287.6 |
| uncovered_mm | 185.1 |
| stretches | 111 |

Basis: filled ground zones in the board file, sampled every 0.5 mm along the tracks.

### SPINE_OUT: 87% of its 32 mm has no ground copper on the other layer

`layout.return_path` · nets: SPINE_OUT · confidence: medium

SPINE_OUT (addressable-LED data (800 kHz, nanosecond edges)). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 18 stretch(es) without cover.

| | |
|---|---|
| length_mm | 31.6 |
| uncovered_mm | 27.7 |
| stretches | 18 |

Basis: filled ground zones in the board file, sampled every 0.5 mm along the tracks.

### USB_DM: 75% of its 83 mm has no ground copper on the other layer

`layout.return_path` · nets: USB_DM · confidence: medium

USB_DM (USB data). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 46 stretch(es) without cover.

| | |
|---|---|
| length_mm | 83.1 |
| uncovered_mm | 62.5 |
| stretches | 46 |

Basis: filled ground zones in the board file, sampled every 0.5 mm along the tracks.

### USB_DP: 79% of its 98 mm has no ground copper on the other layer

`layout.return_path` · nets: USB_DP · confidence: medium

USB_DP (USB data). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 54 stretch(es) without cover.

| | |
|---|---|
| length_mm | 97.7 |
| uncovered_mm | 76.9 |
| stretches | 54 |

Basis: filled ground zones in the board file, sampled every 0.5 mm along the tracks.

### 0.2 mm supply tracks carry up to 826 mA (VLED)

`layout.track_current` · nets: VLED · confidence: low

IPC-2221 gives 0.74 A for a 10 C rise at this width in 35 um copper. VLED: 826 mA, 2 mm at this width. Not every segment carries a net's whole current: check the ones between the source and the loads, and widen or pour them. The resistance also costs voltage: see the droop result.

| | |
|---|---|
| narrowest_mm | 0.2 |
| length_at_that_width_mm | 2.2 |
| capacity_A | 0.74 |
| load_max_mA | 826 |
| loads | D21 43.5 mA, D1 43.5 mA, D2 43.5 mA, D3 43.5 mA, D4 43.5 mA, +14 more |
| drop_mV_at_max | 4.5 |

Basis: IPC-2221 external-layer formula; load is the sum of model maxima, all on at once.

### BZ1 gets about 0.63 V; it is specified from 2 V

`load.inductive` · parts: BZ1, R35, R37 · nets: +3V3 · confidence: medium

BZ1 (MLT-5020): 50R in series (R35, R37) with a 12 ohm coil from +3V3 leaves 0.63 V across it by its DC resistance; it will be much quieter than its rated sound level. The coil's impedance at 4 kHz is higher than its DC resistance, so the real figure is somewhat better: measure it. If the resistors are there to limit the current when the drive pin sticks high, a capacitor in series with the drive, or a time-limited driver, does that without costing volume.

| | |
|---|---|
| supply | +3V3 3.234-3.366 V |
| series_resistance | 50R |
| coil | 12 ohm |
| coil_voltage_dc | 0.63 |
| peak_current_mA | 54 |
| rated | 2.0-4.0 V, 100 mA max |

Basis: part model parts/mlt-5020.yaml (verified against datasheet).

### F1 may carry 1185 mA; its hold current is 1100 mA

`power.budget` · parts: F1 · nets: BAT_P1, BAT_P1F · confidence: medium

F1 (1.1A) feeds BAT_P1F. Sum of the maximum currents of everything behind it: U4 355 mA, D21 43.5 mA, D1 43.5 mA, D2 43.5 mA, D3 43.5 mA, +22 more. This is the all-on worst case; if firmware limits it, record the limit in boardlint.yaml.

| | |
|---|---|
| through_mA_max | 1185 |
| rating_mA | 1100.0 |
| loads | U4 355 mA, D21 43.5 mA, D1 43.5 mA, D2 43.5 mA, D3 43.5 mA, +22 more |

Basis: part model parts/polyfuse-1812-1.1a.yaml (NOT verified against datasheet).

### U3 drops out of regulation when +BATT is below 3.62 V at peak load

`power.regulator` · parts: U3, U4 · nets: +3V3, +BATT · confidence: medium

+BATT spans 3 to 4.2 V. Below 3.62 V with 359 mA drawn the output follows the input down, about 317 mV beneath it. U4 (ESP32-S3-MINI-1-N8) needs 3 V: at peak load that is lost once +BATT is under 3.32 V, well before 3 V. Expect brown-out resets on current peaks with a part-discharged source.

| | |
|---|---|
| load_max_mA | 358.6 |
| load_typ_mA | 95.5 |
| loads | U4 355 mA, U8 2.2 mA, U9 0.5 mA, U7 0.393 mA, U11 0.26 mA, +2 more |
| vin | +BATT 3-4.2 V (U2 charger float voltage; 3.0 V empty cell assumed) |
| dropout | 530 mV at 600 mA, scaled to 317 mV at 359 mA |
| vin_needed | 3.617 |
| brownout_below_vin | 3.32 |

Basis: part model parts/rt9080-33.yaml (verified against datasheet): dropout; load is the sum of model maxima.

### SK6812MINI-012 VDD: VLED can fall to 3 V, below the operating minimum of 3.7 V

`power.supply_range` · parts: D21 · nets: VLED · confidence: high

SK6812 addressable RGB LED, 3.7 x 3.5 x 1.1 mm, 12 mA per colour, single-wire 800 kbit/s: out of specification over the bottom part of the rail's range.

| | |
|---|---|
| rail | VLED 3-4.2 V (+BATT through Q2) |
| part | 3.7-5.5 V, abs max 5.5 V |

Basis: part model parts/sk6812mini-012.yaml (verified against datasheet).

### SK6812SIDE-A VDD: VLED can fall to 3 V, below the operating minimum of 3.7 V

`power.supply_range` · parts: D1 · nets: VLED · confidence: high

SK6812 side-emitting addressable RGB LED, 4.0 x 2.0 x 1.6 mm, 12 mA per colour, single-wire 800 kbit/s: out of specification over the bottom part of the rail's range.

| | |
|---|---|
| rail | VLED 3-4.2 V (+BATT through Q2) |
| part | 3.7-5.5 V, abs max 5.5 V |

Basis: part model parts/sk6812-side-a.yaml (verified against datasheet).

### The board is out of step with the schematic

`sync.schematic_board` · parts: D21, C30, D20, C29, D19 · confidence: high

7 net(s) are connected differently; footprint differs for D21 (schematic LED_SK6812MINI-012_3.7x3.5mm, board LED_SK6812MINI-E_3.2x2.8mm_P1.5mm_ReverseMount); on the board only: C30, D20, C29, D19. This run uses the schematic's netlist; layout findings below describe the old board. Update the board from the schematic before trusting either set of results for the other.

Basis: comparison of the schematic netlist, footprint fields and the board file.

## Notes

### U8: footprint pad(s) 12, 13, 14, 15, 3, 4, 5, 6 have no pin on the symbol

`footprint.pin_map` · parts: U8 · confidence: medium

U8 (QMC5883P), symbol DinoLight:QMC5883P, footprint Package_LGA:LGA-16_3x3mm_P0.5mm. They are unconnected on the board. Fine for mounting tabs; a mistake if the part has a function there (exposed pad, second row).

Basis: pin numbers in the schematic symbol against pad numbers in the board file.

### I2C bus SDA / SCL address map

`i2c.bus` · parts: U10, U11, U5, U7, U8, U9 · nets: SCL, SDA · confidence: high

0x29 U10 LTR-303ALS-01 (fixed); 0x2C U8 QMC5883P (fixed); 0x44 U9 SHT40-AD1B (fixed); 0x46 U11 BMP580 (U11.5(SDO)=0); 0x5C U7 MPR121QR2 (U7.4(ADDR) on SDA); 0x6A U5 LSM6DS3TR-C (U5.1(SDO/SA0)=0)

### I2C net SCL leaves the board with 2.2k already fitted

`i2c.bus` · nets: SCL · confidence: medium

Breakout modules usually carry their own pull-ups (2.2k to 10k each); every one plugged in lowers the total. Budget for the 3 mA limit.

| | |
|---|---|
| pullups | {'R18': '2.2k'} |
| effective | 2.2k |
| rail | +3V3 |
| r_min_3mA | 989R |
| bus_c_est_pF | 147 |
| t_rise_ns | 274 |

### I2C net SDA leaves the board with 2.2k already fitted

`i2c.bus` · nets: SDA · confidence: medium

Breakout modules usually carry their own pull-ups (2.2k to 10k each); every one plugged in lowers the total. Budget for the 3 mA limit.

| | |
|---|---|
| pullups | {'R17': '2.2k'} |
| effective | 2.2k |
| rail | +3V3 |
| r_min_3mA | 989R |
| bus_c_est_pF | 157 |
| t_rise_ns | 293 |

### EYE_DIN couples into PAD_SPINE1 (capacitive-touch electrode of U7)

`layout.coupling` · nets: EYE_DIN, PAD_SPINE1 · confidence: low

EYE_DIN (addressable-LED data (800 kHz, nanosecond edges)) runs 3 mm side by side on one layer, down to 0.45 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.07 pF to a line toggling 3.3 V can show up as touch noise or false touches while that line is active. Estimated 0.07 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.067 |
| side_by_side_mm | 2.8 |
| min_gap_mm | 0.45 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 0.0 |
| aggressor | EYE_DIN: addressable-LED data (800 kHz, nanosecond edges), 3.3 V swing |
| victim | PAD_SPINE1: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### Net classes used for coupling: 26 aggressor, 28 victim net(s)

`layout.coupling` · confidence: medium

Aggressors: EYE_DATA, EYE_DIN, SCL, SPINE_1, SPINE_10, SPINE_11, SPINE_12, SPINE_13, SPINE_14, SPINE_15, SPINE_16, SPINE_17, SPINE_2, SPINE_3.... Victims: EN, LDO_EN, PAD_FLIP_F, PAD_FLIP_R, PAD_SNOUT, PAD_SPINE1, PAD_SPINE2, PAD_SPINE3, PAD_SPINE4, PAD_SPINE5, PAD_SPINE6, PAD_SPINE7, PAD_SPINE8, PAD_TAIL, RST_OD, T_FLIP_F, T_FLIP_R, T_SNOUT, T_SPINE1, T_SPINE2....

### SCL couples into PAD_TAIL (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_TAIL, SCL · confidence: low

SCL (clock) runs 6 mm side by side on one layer, down to 0.47 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.13 pF to a line toggling 3.366 V can show up as touch noise or false touches while that line is active. Estimated 0.13 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.129 |
| side_by_side_mm | 5.7 |
| min_gap_mm | 0.47 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 0.7 |
| aggressor | SCL: clock, 3.366 V swing |
| victim | PAD_TAIL: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### SPINE_OUT couples into PAD_SPINE8 (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_SPINE8, SPINE_OUT · confidence: low

SPINE_OUT (addressable-LED data (800 kHz, nanosecond edges)) runs 4 mm side by side on one layer, down to 0.80 mm apart and 5 mm directly above or below it. A fingertip changes an electrode by around a picofarad or less. 0.22 pF to a line toggling 3.3 V can show up as touch noise or false touches while that line is active. Estimated 0.22 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.222 |
| side_by_side_mm | 3.7 |
| min_gap_mm | 0.8 |
| crossing_over_mm | 4.6 |
| of_which_over_ground_mm | 0.0 |
| aggressor | SPINE_OUT: addressable-LED data (800 kHz, nanosecond edges), 3.3 V swing |
| victim | PAD_SPINE8: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### SPINE_OUT couples into PAD_TAIL (capacitive-touch electrode of U7)

`layout.coupling` · nets: PAD_TAIL, SPINE_OUT · confidence: low

SPINE_OUT (addressable-LED data (800 kHz, nanosecond edges)) runs 4 mm side by side on one layer, down to 0.82 mm apart. A fingertip changes an electrode by around a picofarad or less. 0.08 pF to a line toggling 3.3 V can show up as touch noise or false touches while that line is active. Estimated 0.08 pF; closed-form estimate, not a field solve.

| | |
|---|---|
| coupled_C_est_pF | 0.079 |
| side_by_side_mm | 3.6 |
| min_gap_mm | 0.82 |
| crossing_over_mm | 0.0 |
| of_which_over_ground_mm | 0.0 |
| aggressor | SPINE_OUT: addressable-LED data (800 kHz, nanosecond edges), 3.3 V swing |
| victim | PAD_TAIL: capacitive-touch electrode of U7 |

Basis: coplanar-strip and parallel-plate capacitance formulas on the board geometry; net classes from pin roles (override in boardlint.yaml net_classes:).

### EYE_DATA: 100% of its 19 mm has no ground copper on the other layer

`layout.return_path` · nets: EYE_DATA · confidence: medium

EYE_DATA (addressable-LED data (800 kHz, nanosecond edges)). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 15 stretch(es) without cover.

| | |
|---|---|
| length_mm | 19.4 |
| uncovered_mm | 19.4 |
| stretches | 15 |

Basis: filled ground zones in the board file, sampled every 0.5 mm along the tracks.

### SPINE_DATA: 94% of its 13 mm has no ground copper on the other layer

`layout.return_path` · nets: SPINE_DATA · confidence: medium

SPINE_DATA (addressable-LED data (800 kHz, nanosecond edges)). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 6 stretch(es) without cover.

| | |
|---|---|
| length_mm | 13.4 |
| uncovered_mm | 12.6 |
| stretches | 6 |

Basis: filled ground zones in the board file, sampled every 0.5 mm along the tracks.

### UART_TX: 78% of its 24 mm has no ground copper on the other layer

`layout.return_path` · nets: UART_TX · confidence: medium

UART_TX (UART). Where the reference copper is missing the return current detours, the loop area grows, and the trace both radiates and picks up more. 22 stretch(es) without cover.

| | |
|---|---|
| length_mm | 24.3 |
| uncovered_mm | 18.9 |
| stretches | 22 |

Basis: filled ground zones in the board file, sampled every 0.5 mm along the tracks.

### +BATT: about 151 mV lost in 104 mm of 0.4 mm track at 1185 mA

`layout.track_current` · nets: +BATT · confidence: low

If that length is in series with the load, it is 128 mohm.

| | |
|---|---|
| narrowest_mm | 0.4 |
| length_at_that_width_mm | 104.0 |
| capacity_A | 1.23 |
| load_max_mA | 1185 |
| loads | U4 355 mA, D21 43.5 mA, D1 43.5 mA, D2 43.5 mA, D3 43.5 mA, +22 more |
| drop_mV_at_max | 151.4 |

Basis: copper resistivity; assumes the narrow segments are in series.

### LED chain on EYE_DATA

`led.chain` · parts: D21, U4 · nets: EYE_DATA, EYE_DIN · confidence: high

1 LED(s): D21; driven by U4.30(IO48) through R15 (330R).

### LED chain on SPINE_DATA

`led.chain` · parts: D1, U4 · nets: SPINE_DATA, SPINE_DIN · confidence: high

18 LED(s): D1, D2, ... D18; driven by U4.15(IO11) through R14 (330R).

### U4.15(IO11) to D1 DIN: logic high is met in practice, not by the datasheet numbers

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

The LED input threshold rises to 2.94 V when VLED is at 4.2 V. The driver's guaranteed output high is 2.59 V, but that figure is at its rated load current; into a CMOS input it sits near 3.13 V.

| | |
|---|---|
| driver_rail | +3V3 3.234-3.366 V |
| driver_voh_min | 2.59 |
| led_rail | VLED 3-4.2 V |
| led_vih | 2.10-2.94 V (0.7 x VDD) |

Basis: part model parts/sk6812mini-012.yaml (verified against datasheet): VIH.

### U4 pin use: 19 pins in use

`mcu.pin_use` · parts: U4 · confidence: medium

IO0 = BOOT: button [ok; strapping pin]; IO1 = TOUCH_IRQ: interrupt in (U7) [ok: can wake from deep sleep]; IO3 = IO3: test point only [ok; strapping pin]; IO4 = BUZZ: digital out (to FET gate) [ok]; IO10 = VBAT_SENSE: analog in (+BATT through R6/R7) [ok: ADC1]; IO11 = SPINE_DATA: addressable-LED data out (D1) [ok]; IO15 = ACC_INT1: interrupt in (U5) [ok: can wake from deep sleep]; IO16 = ACC_INT2: interrupt in (U5) [ok: can wake from deep sleep]; IO17 = CHG_STAT: digital in (divided from CHG_STAT_5V) [ok]; IO18 = VBUS_DET: digital in (divided from VBUS) [ok]; USB_D- = USB_DM: USB D- (J1) [ok]; USB_D+ = USB_DP: USB D+ (J1) [ok]; IO21 = LED_EN: digital out (to FET gate) [ok]; IO48 = EYE_DATA: addressable-LED data out (D21) [ok]; IO41 = SDA: I2C SDA (U7) [ok]; IO42 = SCL: I2C SCL (U7) [ok]; TXD0 = UART_TX: test point only [ok]; RXD0 = UART_RX: test point only [ok]; EN = EN: button [ok]

| | |
|---|---|
| IO0 | BOOT: button [ok; strapping pin] |
| IO1 | TOUCH_IRQ: interrupt in (U7) [ok: can wake from deep sleep] |
| IO3 | IO3: test point only [ok; strapping pin] |
| IO4 | BUZZ: digital out (to FET gate) [ok] |
| IO10 | VBAT_SENSE: analog in (+BATT through R6/R7) [ok: ADC1] |
| IO11 | SPINE_DATA: addressable-LED data out (D1) [ok] |
| IO15 | ACC_INT1: interrupt in (U5) [ok: can wake from deep sleep] |
| IO16 | ACC_INT2: interrupt in (U5) [ok: can wake from deep sleep] |
| IO17 | CHG_STAT: digital in (divided from CHG_STAT_5V) [ok] |
| IO18 | VBUS_DET: digital in (divided from VBUS) [ok] |
| USB_D- | USB_DM: USB D- (J1) [ok] |
| USB_D+ | USB_DP: USB D+ (J1) [ok] |
| IO21 | LED_EN: digital out (to FET gate) [ok] |
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

### U10.5(INT) needs a pullup

`pin.requirements` · parts: U10 · confidence: high

U10 (LTR-303ALS-01): the pin is not connected. INT is an open-drain output: Rp3, 1 k to 10 k, to the bus supply. Applies when: the interrupt is used (it is disabled and high impedance by default).

Basis: part model parts/ltr-303als.yaml (verified against datasheet).

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

### 39 capacitor(s) on known rails carry no voltage rating in the schematic

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

### I2C bus SDA / SCL: 5 of 5 modelled target(s) answer in simulation

`sim.i2c` · parts: U10, U11, U5, U7, U8 · nets: SCL, SDA · confidence: high

U10 at 0x29 (register 0x86 = 0xA0); U11 at 0x46 (register 0x01 = 0x50); U5 at 0x6A (register 0x0F = 0x6A); U7 at 0x5C (register 0x5C = 0x10); U8 at 0x2C (register 0x00 = 0x80). Full address scan found 5 responder(s).

Basis: behavioural Verilog models (boardlint/sim/verilog/i2c_target.v) wired from the netlist; ID registers from the part models.

### 19 of 19 addressable LED(s) latch data in simulation

`sim.led_chain` · parts: D1, D21 · confidence: high

Position along each data line, as simulated: from D1: D1, D2, ... D18; from D21: D21.

Basis: behavioural Verilog model (boardlint/sim/verilog/serial_led.v) wired from the netlist.

## Coverage

| Check | Status | |
|---|---|---|
| `clock.source` | ran | 0 finding(s), 0.00 s |
| `decoupling.per_part` | ran | 2 finding(s), 0.00 s |
| `decoupling.regulator_caps` | ran | 0 finding(s), 0.00 s |
| `footprint.pin_map` | ran | 2 finding(s), 0.00 s |
| `i2c.bus` | ran | 3 finding(s), 0.00 s |
| `layout.coupling` | ran | 8 finding(s), 1.14 s |
| `layout.return_path` | ran | 8 finding(s), 0.57 s |
| `layout.track_current` | ran | 2 finding(s), 0.00 s |
| `led.chain` | ran | 4 finding(s), 0.00 s |
| `load.inductive` | ran | 1 finding(s), 0.00 s |
| `mcu.alt_function` | ran | 0 finding(s), 0.00 s |
| `mcu.pin_use` | ran | 1 finding(s), 0.00 s |
| `mcu.strapping` | ran | 1 finding(s), 0.00 s |
| `pin.floating_control` | ran | 0 finding(s), 0.00 s |
| `pin.name_voltage` | ran | 0 finding(s), 0.00 s |
| `pin.requirements` | ran | 2 finding(s), 0.00 s |
| `pin.strap_strength` | ran | 0 finding(s), 0.00 s |
| `polarity.polarised_parts` | ran | 0 finding(s), 0.00 s |
| `power.budget` | ran | 2 finding(s), 0.00 s |
| `power.droop` | ran | 1 finding(s), 0.82 s |
| `power.logic_level` | ran | 0 finding(s), 0.00 s |
| `power.pin_voltage` | ran | 2 finding(s), 0.01 s |
| `power.rails` | ran | 1 finding(s), 0.00 s |
| `power.regulator` | ran | 1 finding(s), 0.00 s |
| `power.supply_range` | ran | 2 finding(s), 0.00 s |
| `ratings.fets` | ran | 1 finding(s), 0.00 s |
| `ratings.passives` | ran | 1 finding(s), 0.00 s |
| `reset.circuit` | ran | 1 finding(s), 0.00 s |
| `sim.i2c` | ran | 1 finding(s), 0.06 s |
| `sim.led_chain` | ran | 1 finding(s), 0.03 s |
| `spi.bus` | ran | 0 finding(s), 0.00 s |
| `sync.schematic_board` | ran | 1 finding(s), 0.00 s |
| `uart.direction` | ran | 0 finding(s), 0.00 s |
| `usb.wiring` | ran | 0 finding(s), 0.00 s |

## Part models

| Parts | Value | Model | Verified against datasheet |
|---|---|---|---|
| BZ1 | MLT-5020 | mlt-5020 | yes |
| D1, D10, D11, D12 +16 | SK6812SIDE-A | sk6812-side-a | yes |
| D21 | SK6812MINI-012 | sk6812mini-012 | yes |
| D23, D24 | 1N4148W | 1n4148w | no |
| F1 | 1.1A | polyfuse-1812-1.1a | no |
| J1 | USB-C | usb-c-hro-type-c-31-m-12 | yes |
| J2 | LiPo JST-PH | **none: heuristics only** |  |
| J3 | Qwiic | **none: heuristics only** |  |
| Q1, Q2 | AO3401A | ao3401a | yes |
| Q3 | 2N7002 | 2n7002 | yes |
| Q4 | AO3400A | ao3400a | yes |
| SW1 | MSK12C02 | msk12c02 | yes |
| SW2 | RESET | ts-1187a | yes |
| SW3 | BOOT | ts-1187a | yes |
| U1 | USBLC6-2SC6 | usblc6-2 | yes |
| U10 | LTR-303ALS-01 | ltr-303als | yes |
| U11 | BMP580 | bmp580 | yes |
| U2 | MCP73831T-2ACI/OT | mcp73831 | yes |
| U3 | RT9080-33GJ5 | rt9080-33 | yes |
| U4 | ESP32-S3-MINI-1-N8 | esp32-s3-mini-1 | yes |
| U5 | LSM6DS3TR-C | lsm6ds3tr-c | yes |
| U6 | TLV803SDBZR | tlv803s | yes |
| U7 | MPR121QR2 | mpr121 | yes |
| U8 | QMC5883P | qmc5883p | yes |
| U9 | SHT40-AD1B | sht40 | no |

## Known issues of the parts used

From errata sheets and forums, recorded in the part models. Not checked against this design.

- **SK6812SIDE-A** (3v3-data-with-5v-supply): VIH is 0.65 x VDD, 3.25 V at a 5 V supply (3.58 V at 5.5 V): a 3.3 V MCU output (guaranteed high level typically 0.8 x 3.3 V = 2.64 V) does not meet it, so the first LED's DIN needs a level shifter or a lower LED supply (VDD of 4.0 V or less for 2.64 V). Source: datasheets/C5378721.pdf IC electrical parameters p.6; https://learn.adafruit.com/neopixel-levelshifter/shifting-levels
- **SK6812MINI-012** (3v3-data-with-5v-supply): VIH is 0.7 x VDD, 3.5 V at a 5 V supply (2.59 V at the 3.7 V minimum, 2.94 V at 4.2 V): a 3.3 V logic output does not reach it at 5 V, so the first LED's DIN needs a level shifter or a lower LED supply. Source: datasheets/C2886570_SK6812mini-012.pdf, IC electrical parameters p.6
- **ESP32-S3-MINI-1-N8** (usb-pins-glitch-at-power-up): GPIO19/GPIO20 (USB D-/D+) are not quiet at power-up: Espressif documents high-level glitches of about 60 us on both and D+ toggling until the USB pull-up settles, so anything else wired to these pins sees pulses at power-up and reset. Source: https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html ; forum report of GPIO20 held high about 170 ms during boot: https://esp32.com/viewtopic.php?t=36423
- **ESP32-S3-MINI-1-N8** (strap-io0-low-io46-high-invalid): IO46 high together with IO0 low at reset is not a defined boot mode (the ESP32-S3 Series Datasheet calls the combination invalid); do not pull IO46 up. Source: https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf (section Boot Configurations); module datasheet Table 4-3
- **ESP32-S3-MINI-1-N8** (strap-io45-high-selects-1v8-flash-supply): IO45 high at reset switches VDD_SPI, the supply of the in-package flash, from 3.3 V to the 1.8 V regulator; keep IO45 low or floating during reset unless that is intended. Source: datasheets/ESP32-S3-MINI-1_en.pdf Table 4-4, p.15
- **MPR121QR2** (early-datasheet-wrong-address): Rev 0 (9/2009) of the datasheet and of AN3895 gave a wrong I2C address; the address with ADDR at VSS is 0x5A (as in Rev 4), so do not rely on copies of the old revision. Source: https://community.nxp.com/thread/62485
- **MPR121QR2** (read-needs-repeated-start): Register reads need a repeated START between the register-address write and the read; a STOP in between has been reported to make every register read back as zero. Source: https://community.nxp.com/t5/Sensors/MPR121-all-registers-read-zero/m-p/228651 ; datasheet read format p.22
