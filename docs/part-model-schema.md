# Part model schema

A part model is one YAML document in `boardlint/library/parts/` holding the datasheet facts the
checks need. Models are produced **offline** (by a person, or by an LLM reading the datasheet with
`tools/extract_prompt.md`), reviewed, and committed. The checker itself never calls an LLM.

Every field except `id` and `match` is optional: a check that needs a missing field is skipped and
says so. Units: volts, ohms, farads (KiCad-style strings such as `100n`, `4.7u`, `75k` are accepted),
milliamps where the key ends in `_ma`, millimetres where it ends in `_mm`.

```yaml
id: rt9080-33                 # unique, lower case
match:                        # how a schematic component is recognised (most specific wins)
  lcsc: [C841192]             # LCSC/JLCPCB part numbers (exact)
  value: ["RT9080-33*"]       # globs tried against Value and MPN-like properties
  lib: []                     # globs tried against the KiCad symbol name (weakest; avoid if the
                              # symbol is commonly borrowed for other parts)
kind: IC                      # optional override: IC, LED, Q, D, CONN, SW, FUSE
class: ldo                    # free text category
description: 600 mA, 2 uA Iq LDO, 3.3 V fixed
datasheet: "Richtek DS9080-05 (datasheets/C841192.pdf)"
provenance:                   # be honest: reviewers decide how much to trust a finding from this
  source: "datasheets/C841192.pdf"
  verified: true              # true only if every number below was read from the source
  notes: "dropout read from the electrical characteristics table, p.4"

supplies:                     # one entry per supply domain of the part
  - pins: [VIN]               # pin names as on the datasheet (aliases split on '/'), or "#3" for pin number 3
    vmin: 1.2                 # recommended operating range
    vmax: 5.5
    abs_max: 6.5              # absolute maximum
    i_typ_ma: 0.002           # current this part itself draws from the supply
    i_max_ma: 0.004
    i_step_ma: 0              # largest fast load step the part produces (for the droop simulation)
    i_step_tr_us: 1           # its rise time
    decoupling:               # what the datasheet asks for on this supply
      - {c_min: 1u, count: 1, max_mm: 5, note: "input capacitor, close to VIN"}

io:                           # defaults for the part's digital pins
  vih_frac: 0.75              # input-high threshold as a fraction of the pin's supply ...
  vil_frac: 0.25
  vih: null                   # ... or absolute thresholds in volts
  vil: null
  voh_frac: 0.8               # guaranteed output high as a fraction of supply
  abs_max_over_supply: 0.3    # a pin may exceed its supply by this much
  abs_max: 3.6                # or an absolute limit
  tolerant_5v: false

pins:                         # only pins that need saying something about
  EN:
    role: enable              # see "Roles"
    active: high
    vih: 0.9                  # per-pin overrides of io:
    vil: 0.4
    abs_max: 6.5
    internal_pull: none       # none | up | down, and optionally internal_pull_ohm
    drive: input              # input | push_pull | open_drain | tri_state | analog
    require:                  # connections the datasheet demands; each is checked on the netlist
      - {not_floating: true}
  VOUT: {role: power_out}
  NC:   {role: nc}

regulator:                    # for regulators
  type: ldo                   # ldo | buck | boost | charge_pump
  vin: VIN
  vout: VOUT
  en: EN
  vout_v: 3.3                 # fixed output; for adjustable parts give vref and fb instead
  vref: null
  fb: null
  tol: 0.02
  i_max_ma: 600
  dropout_mv: 310             # at dropout_at_ma
  dropout_at_ma: 600
  cin_min: 1u                 # effective capacitance, after DC-bias derating
  cout_min: 1u
  bw_khz: 50                  # loop bandwidth if stated (used by the droop model; default 50)
  theta_ja: 230               # C/W
  tj_max: 125
```

Other optional sections, each used by one check family:

```yaml
charger:    {vin: VDD, vbat: VBAT, prog: PROG, stat: STAT, ma_kohm: 1000, v_float: 4.2}   # I = ma_kohm / Rprog[kohm]
i2c:        {addresses: [0x5A], max_khz: 400,
             address_pin: {pin: ADDR, map: {GND: 0x5A, VDD: 0x5B, SDA: 0x5C, SCL: 0x5D}},   # strap by net
             address_bits: {base: 0x18, pins: [{pin: SA0, bit: 0, default: 1}]}}           # or strap by level
spi:        {modes: [0, 3], max_mhz: 10}
serial_led: {protocol: sk6812, vih_frac: 0.7, i_max_ma: 36, i_idle_ma: 0.6, khz: 800}
fet:        {channel: p, vds_max: 30, vgs_max: 12, id_max_a: 4, vgs_th_max: 1.3,
             rds_on: [{vgs: 4.5, mohm: 60}, {vgs: 2.5, mohm: 85}]}
diode:      {vr_max: 75, if_max_ma: 150, vf: 0.7}
fuse:       {i_hold_a: 1.1, i_trip_a: 2.2, v_max: 6, r_min: 0.04, r_max: 0.21}
switch:     {i_max_ma: 50, v_max: 12}
mcu:        {strapping: {IO0: {boot_high: "normal boot"}, IO46: {must_be: low}}}
sim:        {model: i2c_target, params: {ID_REG: 0x0F, ID_VAL: 0x33}}   # Verilog model binding, see docs/simulation.md
errata:                       # known issues from errata sheets and forums; reported with the review
  - {id: short-name, summary: "one sentence", source: "URL or document", severity: info}
```

## Roles

`role` tells the protocol checks what a pin does, from the point of view of **this part**:

| Role | Meaning |
|---|---|
| `i2c_sda`, `i2c_scl` | I2C data / clock |
| `i2c_addr` | address strap |
| `uart_tx`, `uart_rx` | this part transmits / receives on the pin |
| `spi_sck`, `spi_sdi`, `spi_sdo`, `spi_cs` | SDI = data into this part, SDO = data out of it (the part's own point of view) |
| `spi_mosi`, `spi_miso` | the controller-out / controller-in line, for pins named that way on either end |
| `spi_ctrl_sck`, `spi_ctrl_cs` | fixed-function controller pins of an MCU |
| `qspi_io0`..`qspi_io3` | quad SPI data |
| `led_din`, `led_dout` | addressable LED data in / out |
| `usb_dp`, `usb_dm`, `usb_cc`, `usb_vbus` | USB |
| `enable`, `reset`, `boot_strap` | must have a defined level |
| `irq` | interrupt output (give `drive: open_drain` if it needs a pull-up) |
| `gpio` | freely assignable MCU pin: takes whatever role the other end of the net implies |
| `power_in`, `power_out`, `gnd`, `nc`, `analog_in`, `touch` | what they say |

## `require` vocabulary

| Entry | Passes when |
|---|---|
| `{not_floating: true}` | the pin's net has a driver, a pull resistor or a rail on it |
| `{tie: gnd}` / `{tie: supply}` | the pin is on a ground / supply net, directly or through at most 10k |
| `{pullup: {max: 100k}}` / `{pulldown: {...}}` | a resistor to a rail / ground exists, optionally within `min`..`max` |
| `{cap_to_gnd: {min: 100n}}` | a capacitor of at least `min` (optionally at most `max`) goes from the pin to ground |
| `{res_to_gnd: {value: 75k, tol: 0.01}}` | a resistor of that value goes from the pin to ground |

Each entry may carry `note:` (shown in the finding) and `when:` (a condition in words, shown but not evaluated).
