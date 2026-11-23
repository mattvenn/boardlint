# Simulation

boardlint runs two kinds of simulation. Both are generated from the netlist, both are small, and
both are meant to answer one question each. Neither is sign-off.

Set `BOARDLINT_SIM_DIR=some/dir` (or `sim: {keep_dir: ...}` in `boardlint.yaml`) to keep the
generated netlists and testbenches so you can open and change them.

## Rail droop (ngspice): `power.droop`

For every LDO with a part model, one transient run per corner:

```
 Vsrc --Rsrc--+-- vin --[ LDO ]-- out --Rtr--Ltr-- load
              |                    |                 |
          input caps          output caps       output caps nearer the load
              |                                      |
           I_agg (other loads on the input rail)   I_load (step: typical -> maximum)
```

| Element | Where the number comes from | Default when unknown |
|---|---|---|
| `Vsrc` | input rail minimum and mid-range (`power.rails`) | |
| `Rsrc` | sum of what is in the power path: fuse `r_max`, FET `rds_on` at the lowest specified gate voltage, 10 mohm per jumper, plus the source itself | 0.15 ohm for a cell and its protection, 0.1 ohm otherwise. Override with `sources: {NET: {r: 0.08}}` |
| LDO | PI current loop crossing over at `regulator.bw_khz`; pass current limited by the current limit and by `(Vin - Vout) / R_dropout`, with `R_dropout = dropout_mv / dropout_at_ma` | 50 kHz crossover; limit 1.3 x `i_max_ma` |
| Capacitors | every capacitor on the rail, value derated for DC bias by package, ESR and ESL by package | 0603 |
| `Rtr`, `Ltr` | pad-to-pad distance x 1.4, narrowest track on the net, copper thickness from the stack-up | 20 mohm, 5 nH with no board |
| `I_load` | sum of `i_typ_ma` stepping to sum of `i_max_ma` of the parts on the rail | rise time 10 us (`sim: {load_tr_us: ...}`) |
| `I_agg` | everything else fed from the regulator's input rail (LED strings, motors), switching at the same instant | |

Reported: the minimum and settled voltage at the load and the minimum input voltage, per corner,
against the highest `vmin` of the parts on the rail.

What it does not model: the regulator's real loop (PSRR, slew limits, foldback), battery
dynamics beyond a resistor, plane inductance, thermal effects. Treat a failure as "work this out
properly", and a pass as "no obvious problem".

Switching regulators are not simulated yet.

## Bus simulation (Icarus Verilog): `sim.i2c`, `sim.led_chain`

The netlist becomes a Verilog module:

- every net is a `wire`; nets joined through series resistors (up to 1k), ferrites or closed jumpers are one wire
- supply rails are `supply1`, grounds are `supply0`
- a net with a pull-up resistor to a rail gets `pullup(...)`; with a pull-down, `pulldown(...)`
- a part whose model has a `sim:` section is instantiated with its pins on those wires
- the testbench plays the MCU on the bus nets

This is four-state simulation: a line with no pull-up reads `z`, two drivers fighting read `x`.
That is why it uses Icarus rather than Verilator, which is two-state and has limited tri-state
support. The models are behavioural and are not synthesisable.

### I2C

`i2c_target.v` answers at an address given by the board's own strap wiring, only while its supply
pins are at 1, its ground pins at 0 and its mode pins (`sim.enable`) at the right level. It returns
`ID_VAL` when `ID_REG` is read.

The testbench:

1. releases both lines and reports their level (a missing pull-up shows as `z`)
2. writes every address from 0x08 to 0x77 and records which are acknowledged, and by how many targets
3. for each modelled target, reads its ID register at the address where it answered

Findings: bus does not idle high; a target never answers; two targets answer one address; an ID
reads back wrong; the address found differs from the static strap analysis.

The static `i2c.bus` check already catches a crossed SDA/SCL or a missing pull-up. The simulation
adds the cases that come from several facts at once: a mode pin strapped the wrong way, a supply
pin left off, a strap that resolves to an unexpected address.

### Addressable LEDs

`serial_led.v` decodes bits by their high time, keeps the first 24 after a reset and forwards the
rest. It works only while its supply and ground are connected. `LEVEL_OK = 0` (set when the
driver's high level cannot reach the first LED's input threshold) makes its input unknown.

The testbench clocks one frame into every chain head, with word *k* carrying the value *k*, and
reads back what each LED latched. That gives the position of every LED along its chain, and the
LEDs that got nothing.

### Adding a model

1. Put a behavioural Verilog module in `boardlint/sim/verilog/`.
2. Bind it in the part model: `sim: {model: <module>, params: {...}, enable: [{pin: CS, level: 1}]}`.
3. Add a testbench generator next to the existing ones in `boardlint/sim/busgen.py`.

Planned: SPI and QSPI flash (JEDEC ID read), UART loop-back with level and direction, device-specific
models where a known erratum changes bus behaviour.
