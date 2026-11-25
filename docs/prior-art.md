# Prior art (checked 2026-11-23)

What already exists for reviewing a KiCad design beyond ERC/DRC, and what boardlint should reuse.

**How this was verified.** Rows without a mark had their repository or PyPI page opened during the
survey. **(S)** means search-result snippets only. **(U)** means unverified. `docs.kicad.org`,
`forum.kicad.info` and `nlnet.nl` were not reachable from the survey session, and no commercial
vendor site was opened, so the whole commercial table is (S).

## 1. Review tools beyond ERC/DRC

| Name | Licence | Last activity | What it does | Verdict |
|---|---|---|---|---|
| [kicad-happy](https://github.com/aklofas/kicad-happy) | MIT | 2026 (v3.0.2) | The closest prior art. Zero-dependency Python analysers with LLM skills on top, KiCad 5 to 10. I2C pull-ups with rise time, SPI chip-select counts, UART voltage domains, decoupling, power tree and budget, derating, ngspice testbenches, 44 EMC rules, a datasheet-to-JSON cache. On the board: decoupling distance, grid-based proximity, reference-plane changes. | Reuse or contribute |
| [Revlo](https://github.com/rebels-software/revlo-cli) | Apache-2.0 | 2026 (alpha) | Deterministic rules (power, decoupling, I2C pull-ups) plus LLM datasheet review with your own key. JSON rule packs, baselines, waivers, CI mode. | Borrow ideas |
| [kicad-tools](https://github.com/rjwalters/kicad-tools) | MIT | 2026 | Pure-Python KiCad 8+ parser; `kct analyze` (SI, ratings, component stress), creepage, KiCad-free DRC. | Reuse parser |
| [VelaTrace](https://github.com/F-Blaze/VelaTrace) | MIT | 2026 (alpha) | KiCad 10 plugin, Windows only, no headless mode. I2C pull-ups, LED resistors, swapped D+/D-, strap pins, crystal capacitors. | Borrow ideas |
| [kicad-mcp-pro](https://github.com/oaslananka/kicad-mcp-pro) | AGPL-3.0 | 2026 | MCP server with closed-form SI/PI/EMC/thermal estimates. | Borrow ideas |
| KiCAD-MCP-Server, kicad-mcp, mcp-server-kicad | MIT / MIT / GPL-3 | 2025-2026 | Design automation; they only wrap ERC/DRC. | Ignore |
| [KiBot](https://github.com/INTI-CMNB/KiBot) | AGPL-3.0 | 2026 | Preflights wrap ERC/DRC, field checks, zone fills. No semantic checks. | Use as CI host |
| [SKiDL](https://github.com/devbisme/skidl) | MIT | 2026 | ERC on pin-type conflicts, undriven nets, unconnected pins. | Ignore |
| [atopile](https://github.com/atopile/atopile) | MIT | 2026 | `requires_pulls` on I2C is active; the unique-address check is commented out on main. Only for designs written in ato. | Borrow ideas |
| KiCad custom DRC rules (master) | GPL-3 (U) | 2026 | Has `return_path`, `diff_pair_uncoupled`, `skew`, `length`, `via_count`, `creepage`, `assertion`. No crosstalk constraint. Not confirmed for the 9.0 branch. | Reuse |
| DRCY (AllSpice), Traceformer, eSim-Inspect | closed / ? / ? | 2026 | LLM datasheet review; a student plugin. (S) | Borrow ideas |

## 2. Parsers

| Name | Licence | Last activity | KiCad 8/9/10 | Verdict |
|---|---|---|---|---|
| `kicad-cli sch export netlist` | GPL-3 | current | Yes. Formats: kicadsexpr, kicadxml, spice and others. | Reuse as ground-truth connectivity when KiCad is installed |
| kinparse | MIT | 2025 | Netlists from KiCad 5 to 9. | Reuse |
| [askiff](https://github.com/antmicro/askiff) | Apache-2.0 | 2026 | 8+, full KiCad 10, round-trip. | Reuse candidate |
| kicad-happy `kicad_core/sexp.py`, kicad-tools | MIT | 2026 | 5 to 10 / 8+. | Reuse |
| kicadfiles, kicad-sch-api | MIT | 2025 | Not checked. | Evaluate |
| sexpdata | BSD-2 | 2024 | Generic S-expressions. | Fallback |
| kiutils | GPL-3 | 2024 (stale) | States "6.0 and up" only. | Ignore |
| kicad-skip | LGPL-2.1 | 2024 (stale) | States 7+. | Ignore |
| kicad-python (IPC API) | MIT | 2026 | Needs a running KiCad 9+; not headless. | Ignore for CI |

## 3. Signal and power integrity from a script

| Name | Licence | Last activity | Does | Verdict |
|---|---|---|---|---|
| [kisi](https://github.com/riehlies/kisi) | GPL-3.0-only | 2026 | Node CLI on `.kicad_pcb`, JSON output. Impedance, neighbour crosstalk, IR drop, PDN impedance, decaps ranked by loop inductance. Estimates, not sign-off. | Reuse via subprocess |
| [kicad-irdrop](https://github.com/firedanceio/kicad-irdrop) | Apache-2.0 | 2026 (6 commits) | Resistive-mesh DC drop. CLI, JSON, exit codes. Needs `pcbnew`. | Used as the reference in [crosscheck.md](crosscheck.md) |
| [padne](https://github.com/atx/padne) | GPL-3 | 2026 | 2.5D FEM DC drop. Needs KiCad bindings. | Cross-check |
| [KiPI](https://github.com/drewsum/KiPI) | GPL-3 plus no-commercial clauses | 2026 | DC drop, AC PDN impedance, regulator noise coupling. GUI/IPC only. | Borrow ideas |
| [KiCad-Parasitics](https://github.com/Steffen-W/KiCad-Parasitics) | GPL-3 | 2026 | Point-to-point R and loop L (ngspice, bfieldtools). Plugin only. | Borrow ideas |
| gerber2ems, kicad-si-simulation-wrapper (Antmicro) | Apache-2.0 | 2026 | Slices nets from the PCB, runs openEMS, gives S-parameters and impedance. | Reuse for a slow tier |
| openEMS | GPL-3 | 2026 | FDTD solver with Python bindings. | Via gerber2ems |
| pcbmodelgen | GPL-3 | 2023 (stale) | KiCad to openEMS (Octave). | Ignore |
| FastHenry2 / FasterCap | not stated / LGPL-2.1+ | ? | Headless L and C solvers; no PCB import. | Ignore |
| pcb-rnd, sparselizard, KiCad PDN calculator | | | (U) Not opened. | |

## 4. Commercial feature targets (all from search snippets)

- **Siemens Xpedition / HyperLynx Schematic Analysis (ex-Valydate):** 125 to 150+ voltage-aware
  per-net checks from a library of about six million part models: missing power, pin-voltage and
  pin-type mismatch, nets with no receiver.
- **HyperLynx DRC:** 90+ parameterised SI/PI/EMI/safety rules: return path, reference-plane change,
  split crossings, impedance. Custom rules in Python.
- **Cadence Sigrity X Aurora:** in-design crosstalk, return-path quality, IR drop.
- **Altium Signal Analyzer / Power Analyzer (Keysight):** impedance, loss, reflection; DC drop, current density.
- **CADY:** pin-by-pin connections against datasheet limits.
- **AllSpice DRCY:** multi-agent, fetches datasheets itself, posts per-pin verdicts as review comments.
- **Circuit Mind AVE:** agents checking against datasheets, app notes and house rules.
- **Flux Copilot review:** per-pin decoupling, power ratings, missing connections.
- **Cadstrom, Quilter, Schemalyzer:** no public detail / layout generation / EasyEDA only.

## 5. Component data

| Name | Licence | Content | Verdict |
|---|---|---|---|
| [jlcparts](https://github.com/yaqwsx/jlcparts) | MIT | JLC/LCSC catalogue with normalised attributes and datasheet links. | Reuse: LCSC number to MPN, package, rated voltage |
| CDFER/jlcpcb-parts-database | MIT | Daily SQLite build from jlcparts (about 1 GB). | Reuse |
| STM32_open_pin_data | BSD-3 | CubeMX pin database: every alternate function of every STM32 pin. | Reuse for MCU pin roles |
| modm-devices | MPL-2.0 | 5,274 AVR/STM32/SAM/nRF/RP devices. | Reuse |
| [datasheet-cli](https://github.com/akiselev/datasheet-cli) | GPL-3.0-only | LLM to JSON: pins, abs-max, electrical. A tool, not a dataset. | Borrow the schema |
| kicad-happy datasheets skill | MIT | Scored JSON extraction cache. | Borrow the schema |
| easyeda2kicad | AGPL-3.0 | LCSC number to symbol with pin names. | Reuse via subprocess |
| KiCad symbol libraries | CC-BY-SA with exception (U) | Pin electrical types, datasheet URLs. | Already used: embedded in every schematic |
| Nexar / Octopart API | commercial | Specs and datasheet URLs; small free tier. (S) | Optional |

No open database of absolute-maximum or pin-role data was found. Every tool that needs them
extracts them per part with an LLM.

## The gap

Going by kicad-happy's methodology document (its README lists more than the document describes, so
the document may lag the code), nothing open-source was found that covers:

- **UART TX/RX reversal.** kicad-happy pairs the lines; it does not check direction.
- **I2C address clashes.** atopile's address check is disabled.
- **SPI / QSPI pin-role mismatches.**
- **Addressable-LED chain direction (DIN/DOUT).**
- **Digital simulation of the wired buses** with Verilog models.
- **A curated, versioned, per-component model library.** The nearest things are the JSON caches of
  kicad-happy and datasheet-cli.

Partly covered elsewhere:

- **Crosstalk.** kisi and kicad-happy use proximity heuristics, with no aggressor/victim
  classification by what the nets do.
- **Return-path gaps.** KiCad master's `return_path` rule; kicad-happy's reference-plane check.
- **Per-IC decoupling and rail droop.** kisi's PDN impedance; kicad-happy sums capacitance per rail.
