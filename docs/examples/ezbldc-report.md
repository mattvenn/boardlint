# boardlint review: bldc_driver_board

**0 errors, 3 warnings, 11 notes.** 100 components, 76 nets; netlist from the board.

- schematic and board netlists agree (76 multi-pin nets)

## Warnings

### No pull-up on I2C SCL net SCL

`i2c.bus` · parts: U1 · nets: SCL · confidence: high

Devices U1 are open-drain; nothing on the board pulls the line high. The bus leaves the board through a connector, so whatever plugs in may bring them: this board cannot talk I2C on its own, and two boards without pull-ups cannot talk to each other. An MCU's internal pull-up (tens of kilohms) is too weak for 400 kHz.

Basis: I2C specification (UM10204) section 3.1.1.

### No pull-up on I2C SDA net SDA

`i2c.bus` · parts: U1 · nets: SDA · confidence: high

Devices U1 are open-drain; nothing on the board pulls the line high. The bus leaves the board through a connector, so whatever plugs in may bring them: this board cannot talk I2C on its own, and two boards without pull-ups cannot talk to each other. An MCU's internal pull-up (tens of kilohms) is too weak for 400 kHz.

Basis: I2C specification (UM10204) section 3.1.1.

### WS2812B VDD: +3V3 can fall to 3.201 V, below the operating minimum of 3.5 V

`power.supply_range` · parts: D3 · nets: +3V3 · confidence: high

XINGLIGHT XL-5050RGBC-WS2812B, a WS2812B-compatible addressable RGB LED, 5050 package, 12 mA per colour, single-wire 800 kbit/s (LCSC C2843785, listed there as XL-5050RGBC-2812B): out of specification over the bottom part of the rail's range.

| | |
|---|---|
| rail | +3V3 3.201-3.399 V (U1 XIAO-ESP32-S3-Plus output) |
| part | 3.5-5.5 V, abs max 5.5 V |

Basis: part model parts/xl-5050rgbc-ws2812b.yaml (verified against datasheet).

## Notes

### D3 DIN logic level is met

`led.chain` · parts: U1, D3 · nets: LED_DATA · confidence: high

Output high 2.56 V against a threshold of at most 2.38 V.

| | |
|---|---|
| driver_rail | +3V3 3.201-3.399 V |
| driver_voh_min | 2.56 |
| led_rail | +3V3 3.201-3.399 V |
| led_vih | 2.24-2.38 V (0.7 x VDD) |

Basis: part model parts/xl-5050rgbc-ws2812b.yaml (verified against datasheet): VIH.

### LED chain on LED_DATA

`led.chain` · parts: D3, U1 · nets: LED_DATA · confidence: high

1 LED(s): D3; driven by U1.20(D16/GPIO10) directly.

### No series resistor between U1.20(D16/GPIO10) and D3 DIN

`led.chain` · parts: U1, D3 · nets: LED_DATA · confidence: medium

33 to 470 ohm near the driver damps ringing and protects the first LED's input.

### U1 pin use: 20 pins in use

`mcu.pin_use` · parts: U1 · confidence: medium

D0/GPIO1 = M4_IN1: digital out (to U5.27(IN1)) [ok]; D1/GPIO2 = M4_IN3: digital out (to U5.23(IN3)) [ok]; D2/GPIO3 = M3_IN2: digital out (to U4.25(IN2)) [ok; strapping pin]; D3/GPIO4 = DRV_EN: reset out (U2) [ok]; D4/GPIO5/SDA = SDA: to connector J3.3(Pin_3) [ok]; D5/GPIO6/SCL = SCL: to connector J3.4(Pin_4) [ok]; D6/GPIO43/TX = ENC_A0: digital out (to U6.2(1A0)) [ok]; D7/GPIO44/RX = ENC_A1: digital out (to U6.3(1A1)) [ok]; D8/GPIO7 = M2_IN2: digital out (to U3.25(IN2)) [ok]; D9/GPIO8 = M1_IN1: digital out (to U2.27(IN1)) [ok]; D10/GPIO9 = M1_IN3: digital out (to U2.23(IN3)) [ok]; D11/GPIO38 = M4_IN2: digital out (to U5.25(IN2)) [ok]; D12/GPIO39 = M3_IN1: digital out (to U4.27(IN1)) [ok]; D13/GPIO40 = M3_IN3: digital out (to U4.23(IN3)) [ok]; D14/GPIO41 = ENC_CLK: to connector J21.3(Pin_3) [ok]; D15/GPIO42 = ENC_DO_MCU: to connector J21.4(Pin_4) [ok]; D16/GPIO10 = LED_DATA: addressable-LED data out (D3) [ok]; D19/GPIO11 = M2_IN1: digital out (to U3.27(IN1)) [ok]; D18/GPIO12 = M2_IN3: digital out (to U3.23(IN3)) [ok]; D17/GPIO13 = M1_IN2: digital out (to U2.25(IN2)) [ok]

| | |
|---|---|
| D0/GPIO1 | M4_IN1: digital out (to U5.27(IN1)) [ok] |
| D1/GPIO2 | M4_IN3: digital out (to U5.23(IN3)) [ok] |
| D2/GPIO3 | M3_IN2: digital out (to U4.25(IN2)) [ok; strapping pin] |
| D3/GPIO4 | DRV_EN: reset out (U2) [ok] |
| D4/GPIO5/SDA | SDA: to connector J3.3(Pin_3) [ok] |
| D5/GPIO6/SCL | SCL: to connector J3.4(Pin_4) [ok] |
| D6/GPIO43/TX | ENC_A0: digital out (to U6.2(1A0)) [ok] |
| D7/GPIO44/RX | ENC_A1: digital out (to U6.3(1A1)) [ok] |
| D8/GPIO7 | M2_IN2: digital out (to U3.25(IN2)) [ok] |
| D9/GPIO8 | M1_IN1: digital out (to U2.27(IN1)) [ok] |
| D10/GPIO9 | M1_IN3: digital out (to U2.23(IN3)) [ok] |
| D11/GPIO38 | M4_IN2: digital out (to U5.25(IN2)) [ok] |
| D12/GPIO39 | M3_IN1: digital out (to U4.27(IN1)) [ok] |
| D13/GPIO40 | M3_IN3: digital out (to U4.23(IN3)) [ok] |
| D14/GPIO41 | ENC_CLK: to connector J21.3(Pin_3) [ok] |
| D15/GPIO42 | ENC_DO_MCU: to connector J21.4(Pin_4) [ok] |
| D16/GPIO10 | LED_DATA: addressable-LED data out (D3) [ok] |
| D19/GPIO11 | M2_IN1: digital out (to U3.27(IN1)) [ok] |
| D18/GPIO12 | M2_IN3: digital out (to U3.23(IN3)) [ok] |
| D17/GPIO13 | M1_IN2: digital out (to U2.25(IN2)) [ok] |

Basis: part model parts/xiao-esp32-s3-plus.yaml (verified against datasheet): pin capabilities; use inferred from what else is on each net.

### Strapping pin U1.3(D2/GPIO3) is used (M3_IN2)

`mcu.strapping` · parts: U1, U4 · nets: M3_IN2 · confidence: medium

U1 (XIAO-ESP32-S3-Plus) samples this pin at reset (default: floating; boot_high: JTAG from the USB Serial/JTAG controller (only if EFUSE_STRAP_JTAG_SEL = 1); boot_low: JTAG from the pins MTDI / MTCK / MTMS / MTDO, i.e. GPIO41 / 39 / 42 / 40 (only if EFUSE_STRAP_JTAG_SEL = 1); when: ignored with default eFuses). Connected here: U4.25(IN2). Whatever is attached must not hold the wrong level while the module comes out of reset.

Basis: part model parts/xiao-esp32-s3-plus.yaml (verified against datasheet).

### U1.3(D2/GPIO3) must not float

`pin.requirements` · parts: U1 · nets: M3_IN2 · confidence: high

U1 (XIAO-ESP32-S3-Plus): only U4.25(IN2) on the net. GPIO3 selects the JTAG signal source at reset and has no internal pull: its level must be set by an external circuit that cannot be high impedance (S3 2.6.4). Applies when: only if EFUSE_STRAP_JTAG_SEL has been burnt to 1; with the default eFuses GPIO3 is not sampled (DS 3.5.1).

Basis: part model parts/xiao-esp32-s3-plus.yaml (verified against datasheet).

### 12 supply rail(s) with a known voltage

`power.rails` · nets: +12V, +3V3, +5V, /M1_V3P3, /M2_V3P3, /M3_V3P3 · confidence: medium

+12V 11.4-12.6 V (net name); +3V3 3.201-3.399 V (U1 XIAO-ESP32-S3-Plus output); +5V 4.75-5.25 V (U7 L7805CV output); /M1_V3P3 3.079-3.521 V (U2 V3P3 output); /M2_V3P3 3.079-3.521 V (U3 V3P3 output); /M3_V3P3 3.079-3.521 V (U4 V3P3 output); /M4_V3P3 3.079-3.521 V (U5 V3P3 output); /VM1 11.4-12.6 V (+12V through F1); /VM2 11.4-12.6 V (+12V through F2); /VM3 11.4-12.6 V (+12V through F3); /VM4 11.4-12.6 V (+12V through F4); XIAO_5V 4.2-5.05 V (+5V through D2)

Basis: regulator models, net names, boardlint.yaml; override with rails: in boardlint.yaml.

### U7 runs at about 72 C at typical load, and would exceed 125 C if the peak load were sustained

`power.regulator` · parts: U7 · confidence: low

Typical: (12.6 - 5) V x 84 mA = 639 mW. Peak: 358 mA, 2724 mW, 176 C if it lasted. 50 C/W from 40 C ambient, no heatsink.

| | |
|---|---|
| load_max_mA | 358.4 |
| load_typ_mA | 84.1 |
| loads | U1 340 mA, D3 36.3 mA, U6 0.16 mA |
| p_typ_mw | 639 |
| tj_typ | 72 |
| tj_peak | 176 |

Basis: part model parts/l7805.yaml (verified against datasheet): theta_ja.

### U1.12(3V3) supplies +3V3: 36 of 700 mA accounted for

`power.source_pin` · parts: U1 · nets: +3V3 · confidence: medium

U1 (XIAO-ESP32-S3-Plus).

| | |
|---|---|
| pin | U1.12(3V3) |
| limit_mA | 700.0 |
| load_max_mA | 36.5 |
| loads | D3 36.3 mA, U6 0.16 mA |
| not_counted | none |

Basis: part model parts/xiao-esp32-s3-plus.yaml (verified against datasheet).

### 18 capacitor(s) on known rails carry no voltage rating in the schematic

`ratings.passives` · confidence: high

Add a Voltage property (or put it in the value, e.g. '10uF 16V') and they will be checked.

### 1 of 1 addressable LED(s) latch data in simulation

`sim.led_chain` · parts: D3 · confidence: high

Position along each data line, as simulated: from D3: D3.

Basis: behavioural Verilog model (boardlint/sim/verilog/serial_led.v) wired from the netlist.

## Coverage

| Check | Status | |
|---|---|---|
| `clock.source` | ran | 0 finding(s), 0.00 s |
| `decoupling.per_part` | ran | 0 finding(s), 0.00 s |
| `decoupling.regulator_caps` | ran | 0 finding(s), 0.00 s |
| `footprint.pin_map` | ran | 0 finding(s), 0.00 s |
| `i2c.bus` | ran | 2 finding(s), 0.00 s |
| `layout.coupling` | ran | 0 finding(s), 0.01 s |
| `layout.return_path` | ran | 0 finding(s), 0.25 s |
| `layout.track_current` | ran | 0 finding(s), 0.01 s |
| `led.chain` | ran | 3 finding(s), 0.00 s |
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
| `power.budget` | ran | 0 finding(s), 0.01 s |
| `power.droop` | ran | 0 finding(s), 0.00 s |
| `power.logic_level` | ran | 0 finding(s), 0.00 s |
| `power.pin_voltage` | ran | 0 finding(s), 0.01 s |
| `power.rails` | ran | 1 finding(s), 0.00 s |
| `power.regulator` | ran | 1 finding(s), 0.00 s |
| `power.source_pin` | ran | 1 finding(s), 0.00 s |
| `power.supply_range` | ran | 1 finding(s), 0.00 s |
| `ratings.fets` | ran | 0 finding(s), 0.00 s |
| `ratings.passives` | ran | 1 finding(s), 0.00 s |
| `reset.circuit` | ran | 0 finding(s), 0.00 s |
| `sim.i2c` | ran | 0 finding(s), 0.00 s |
| `sim.led_chain` | ran | 1 finding(s), 0.07 s |
| `spi.bus` | ran | 0 finding(s), 0.00 s |
| `sync.schematic_board` | ran | 0 finding(s), 0.00 s |
| `uart.direction` | ran | 0 finding(s), 0.00 s |
| `usb.wiring` | ran | 0 finding(s), 0.00 s |

## Part models

| Parts | Value | Model | Verified against datasheet |
|---|---|---|---|
| D1 | SS54 | ss54 | yes |
| D11, D21, D31, D41 | FAULT | **none: heuristics only** |  |
| D2 | SS14 | ss14 | yes |
| D3 | WS2812B | xl-5050rgbc-ws2812b | yes |
| D4 | SMAJ15A | smaj15a | yes |
| F1, F2, F3, F4 | 1.1A | polyfuse-1812-1.1a | no |
| J1 | 12V_IN | **none: heuristics only** |  |
| J11 | MOTOR1 | **none: heuristics only** |  |
| J12 | MOTOR2 | **none: heuristics only** |  |
| J13 | MOTOR3 | **none: heuristics only** |  |
| J14 | MOTOR4 | **none: heuristics only** |  |
| J2 | 12V_OUT | **none: heuristics only** |  |
| J21 | ENC1 | **none: heuristics only** |  |
| J22 | ENC2 | **none: heuristics only** |  |
| J23 | ENC3 | **none: heuristics only** |  |
| J24 | ENC4 | **none: heuristics only** |  |
| J3 | I2C_IN | **none: heuristics only** |  |
| J4 | I2C_OUT | **none: heuristics only** |  |
| U1 | XIAO-ESP32-S3-Plus | xiao-esp32-s3-plus | yes |
| U2, U3, U4, U5 | DRV8313PWPR | drv8313 | yes |
| U6 | 74HC139D | 74hc139 | yes |
| U7 | L7805CV | l7805 | yes |

## Known issues of the parts used

From errata sheets and forums, recorded in the part models. Not checked against this design.

- **WS2812B** (below-minimum-supply-at-3v3): The minimum supply is 3.5 V (full function is promised only from 4.5 V). On a 3.3 V rail the part is outside its datasheet: it often still lights, but blue, which needs the highest forward voltage, dims or drops out first, and nothing is guaranteed. Source: https://datasheet.lcsc.com/datasheet/pdf/40b65f6fea0587c0483bbbd4496835fd.pdf, tables p.4 and p.5, item 7 p.2
- **WS2812B** (3v3-data-with-5v-supply): VIH is 0.7 x VDD, 3.5 V at a 5 V supply: a 3.3 V MCU output cannot reach it, so with a 5 V LED supply the first DIN needs a level shifter. Source: https://datasheet.lcsc.com/datasheet/pdf/40b65f6fea0587c0483bbbd4496835fd.pdf, electrical parameters p.5
- **XIAO-ESP32-S3-Plus** (uart0-tx-boot-messages): GPIO43 (D6) is UART0 TX: the ROM prints boot messages on it at every reset, so a device wired to D6 as a plain logic input sees serial data before firmware takes the pin over. Printing can be turned off by eFuse or register only. Source: https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/esp32-s3_datasheet.pdf section 2.6.3 p.25; Seeed series datasheet Table 5-3 p.52
- **XIAO-ESP32-S3-Plus** (power-up-glitches): GPIO1 to GPIO14 drive a low-level glitch of about 60 us at chip power-up (GPIO18 to GPIO20 also a high-level one): outputs wired to them are not quiet until firmware runs. Source: https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/esp32-s3_datasheet.pdf Table 2-2 p.14-15
- **XIAO-ESP32-S3-Plus** (dx-names-differ-between-variants): D11 and D12 are GPIO38 / GPIO39 on the Plus but GPIO42 / GPIO41 on the Sense; D13 to D19 exist on the Plus only. Use GPIO numbers in firmware and check the symbol against the variant fitted. Source: Seeed XIAO ESP32-S3 Series Datasheet v1.0, Table 3-5 p.35 and Table 3-11 p.39
- **XIAO-ESP32-S3-Plus** (gpio10-adc-bat-has-no-divider): GPIO10 (D16) is called ADC_BAT in the Arduino board package and on the schematic, but the Plus has no battery divider on it: without an external divider it reads nothing useful, and with one the pin is no longer free. Source: Seeed XIAO ESP32-S3 Series Datasheet v1.0, section 5.5.4 p.58 and 8.1.2 p.84; Plus schematic V1.1 sheet 03
