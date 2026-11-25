# Cross-check of the copper extraction against kicad-irdrop

This note compares boardlint's copper extraction with an independent solver,
[kicad-irdrop](https://github.com/firedanceio/kicad-irdrop) (Apache-2.0, commit `b508349`), on four
real boards, and records what the comparison changed. It was done by Claude (Anthropic's AI
model) on 2026-11-25. Neither tool has been compared with a measurement.

## Why

The extraction ([copper-extraction.md](copper-extraction.md)) had been tested only against cases
worked out by hand. kicad-irdrop solves the same problem in a different way: it reads the board
through KiCad's own `pcbnew` module and rasterises every pad, track and pour of a net on a fine
grid (0.05 mm by default), then solves the resistor mesh directly. boardlint reads the file with
its own parser, treats tracks as one-dimensional resistors, and meshes only the pours. If the two
agree, the reading of the file and the solve are both likely to be right.

KiCad is needed only for this comparison, because kicad-irdrop imports `pcbnew`. boardlint itself
still runs without KiCad.

## Method

- 38 pad-to-pad cases on four boards: 1 A from one source part to one load part on a supply net.
- The same assumptions on both sides: 35 µm copper on every layer, 20 µm via plating, copper at 20 °C.
- kicad-irdrop was run at three grids (0.05, 0.025 and 0.0125 mm), because its answer depends on
  the grid. The pour net on ezbldc was run at 0.05 mm only (3 million cells).
- Where the tools disagreed about whether two pads are joined, KiCad's design rules check (DRC)
  was the referee.

## Result

37 cases: median 1.6 %, mean 2.6 %, worst 8.0 %; 33 within 5 %, 37 within 10 %; boardlint lower in 24.

**DinoLight, latest (four layers)**

| Net | From → to | boardlint (mΩ) | kicad-irdrop 0.05 mm | 0.025 mm | 0.0125 mm | Difference from its finest grid |
|---|---|---|---|---|---|---|
| +3V3 | U3 → U4 | 168.85 | 177.91 | 172.89 | 171.34 | -1.4 % |
| +3V3 | U3 → U7 | 188.53 | 199.18 | 192.58 | 191.00 | -1.3 % |
| +3V3 | U3 → U10 | 236.38 | 248.18 | 242.03 | 240.09 | -1.5 % |
| +3V3 | U3 → U6 | 135.92 | 143.11 | 138.45 | 137.30 | -1.0 % |
| +3V3 | U3 → U5 | 36.46 | 38.59 | 37.64 | 36.96 | -1.3 % |
| +3V3 | U3 → U11 | 51.23 | 55.37 | 53.49 | 52.46 | -2.3 % |
| +BATT | Q1 → Q2 | 95.85 | 101.50 | 97.83 | 96.35 | -0.5 % |
| +BATT | Q1 → U3 | 11.14 | 11.89 | 11.45 | 11.32 | -1.6 % |
| VLED | Q2 → D18 | 167.45 | 170.19 | 167.97 | 166.71 | +0.4 % |
| VLED | Q2 → D1 | 53.68 | 54.57 | 54.05 | 53.61 | +0.1 % |
| VLED | Q2 → D9 | 111.55 | 112.58 | 111.30 | 110.51 | +0.9 % |
| BAT_RAW | SJ1 → Q1 | 18.76 | 20.67 | 20.18 | 19.82 | -5.3 % |

**DinoLight `4da182c` (two layers)**

| Net | From → to | boardlint (mΩ) | kicad-irdrop 0.05 mm | 0.025 mm | 0.0125 mm | Difference from its finest grid |
|---|---|---|---|---|---|---|
| +3V3 | U3 → U4 | 151.73 | 156.74 | 154.09 | 152.81 | -0.7 % |
| +3V3 | U3 → U6 | 115.16 | 118.75 | 116.67 | 115.64 | -0.4 % |
| +3V3 | U3 → U5 | 42.10 | 44.48 | 43.53 | 42.59 | -1.2 % |
| +BATT | Q1 → Q2 | 151.91 | 153.00 | 151.78 | 151.51 | +0.3 % |
| +BATT | Q1 → U3 | 17.78 | 17.62 | 17.41 | 17.38 | +2.3 % |
| VLED | Q2 → D20 | 154.30 | 159.08 | 155.76 | 154.76 | -0.3 % |
| VLED | Q2 → D1 | 36.51 | 38.44 | 36.88 | 36.69 | -0.5 % |
| BAT_RAW | SJ1 → Q1 | 18.64 | 19.11 | 18.55 | 18.39 | +1.3 % |

**ezbldc (four layers, pours)**

| Net | From → to | boardlint (mΩ) | kicad-irdrop 0.05 mm | 0.025 mm | 0.0125 mm | Difference from its finest grid |
|---|---|---|---|---|---|---|
| +12V | D1 → U7 | 30.60 | 28.89 | 28.87 | 28.79 | +6.3 % |
| +12V | D1 → F1 | 4.91 | 4.59 | 4.56 | 4.55 | +8.0 % |
| +12V | D1 → F4 | 10.12 | 9.46 | 9.42 | 9.39 | +7.8 % |
| +5V | U7 → D2 | 20.29 | 21.69 | 20.65 | 20.60 | -1.5 % |
| +3V3 | U1 → D3 | 12.08 | 11.68 | - | - | +3.4 % |
| +3V3 | U1 → U6 | 9.09 | 8.69 | - | - | +4.5 % |
| +3V3 | U1 → U2 | 16.49 | 15.77 | - | - | +4.6 % |
| +3V3 | U1 → U5 | 17.33 | 16.59 | - | - | +4.5 % |

**Density (four layers)**

| Net | From → to | boardlint (mΩ) | kicad-irdrop 0.05 mm | 0.025 mm | 0.0125 mm | Difference from its finest grid |
|---|---|---|---|---|---|---|
| +5V | A1 → D5 | 289.06 | 304.61 | 298.50 | 296.50 | -2.5 % |
| +5V | A1 → D20 | 137.22 | 147.04 | 144.09 | 142.43 | -3.7 % |
| +5V | A1 → D1 | 167.73 | 180.49 | 175.24 | 173.58 | -3.4 % |
| +5V | A1 → U8 | 152.96 | 165.24 | 160.24 | 158.84 | -3.7 % |
| +3V3 | A1 → U5 | 43.34 | 43.97 | 43.88 | 43.83 | -1.1 % |
| +3V3 | A1 → U7 | 105.65 | 110.89 | 109.51 | 109.35 | -3.4 % |
| +3V3 | A1 → FB1 | 61.31 | 62.91 | 62.75 | 62.66 | -2.2 % |
| AVDD | FB1 → U4 | 25.22 | 27.53 | 26.88 | 26.52 | -4.9 % |
| AVDD | FB1 → U1 | 55.21 | 59.85 | 58.61 | 57.79 | -4.5 % |
| AVDD | FB1 → RV17 | 155.80 | not connected | | | see text |

One case has no reference figure: Density `AVDD`, FB1 → RV17. kicad-irdrop reports the load as
not connected; boardlint gives 155.7 mΩ. KiCad's DRC finds no unconnected items on that board, so
the pads are joined. kicad-irdrop does not join layers through the plated hole of a through-hole
pad, and this route changes layer at a potentiometer pin.

kicad-irdrop's own figure falls as its grid gets finer, by 3 to 7 % from 0.05 mm to 0.0125 mm on
narrow tracks, and it was still falling at the finest grid. boardlint is lower than it in 24 of the
37 cases, by 1 to 2 % where tracks are 0.13 to 0.2 mm wide and by less than 1 % where they are
0.4 mm. That pattern is what a raster error on narrow tracks looks like, so some of the remaining
difference belongs to the reference.

boardlint is higher, by 6 to 8 %, on the ezbldc +12V rail, which runs through two necked pours.
There its pour mesh (0.12 mm on that net) is the coarser of the two.

### Connectivity against KiCad's DRC

| Board | KiCad DRC, unconnected items | boardlint |
|---|---|---|
| DinoLight `4da182c` | 105: GND 79, +3V3 3 (U7 pad 20; U5 pads 2 and 3), BAT_P1 1, others 22 | `layout.ir_drop` reports U7 pad 20, the BAT_P1 break, and the ground in separate pieces. U5 pads 2 and 3 are found by the cross-check script (both tools list them as not reached). The check does not report them: they are strap pins tied to the rail, not supply pins, so no current is drawn through them in the solve |
| DinoLight, latest | 0 | none reported |
| Density | 0 | none reported |
| ezbldc | 0 | none reported |

### Pad geometry

boardlint's pad rectangles (position, size, rotation) were compared with the pad polygons KiCad
computes: all 1353 pads on three boards agree within 0.06 mm.

## What the comparison changed

The first run agreed within 2 % on long tracks and was 20 to 43 % high on the ezbldc pour rail.
Finding out why led to five changes, all on 2026-11-25:

1. **Track inside a pad.** boardlint counted a track at its own width from pad centre to pad
   centre. A 1.8 mm hop from a 2 mm pad to a via was mostly inside the pad, where the copper is
   the pad's width. The stretch inside a pad is now counted at the pad's width, and a track is
   joined to the pad's centre through the pad's own copper. Solder and the part's lead are given
   no credit, which keeps the figure on the high side.
2. **Track inside a via's ring** is shorted by the ring.
3. **Custom pads** (solder jumpers, some QFN pads) use their drawn outline, not a bounding box.
4. **Inner copper.** boardlint assumed 35 µm on every layer when the board file has no stack-up.
   kicad-irdrop assumes 17.5 µm inside, and JLCPCB's help pages say 0.5 oz is its default for
   inner layers (15.2 µm finished). The default is now 35 µm outside and 17.5 µm inside. This is
   the change that moves the findings most: on the latest DinoLight the regulator-to-module path
   goes from 175 to 220 mΩ, and a 0.4 mm inner-layer track is good for 372 mA, not 615 mA.
   Override it in `boardlint.yaml` with `stackup: {outer_cu_um: 35, inner_cu_um: 35}`.
5. **Pour mesh.** The pitch can now go down to 0.1 mm on small pours (it stopped at 0.4 mm), and
   a pad reaches pour within its half size plus 0.7 mm.

A sixth change came from running both tools at once: the solver's dot products used threaded
BLAS, which made one solve take 24 s instead of 0.5 s on a busy machine. They are now plain sums.

## Limits of this check

- It compares two models, not a model with a board. Both use the same resistivity and the same
  via formula, so an error common to both would not show.
- Only direct-current resistance is compared. The impedance and delay figures of
  `layout.impedance` have no independent check. kisi has a 2D field solver that could give one;
  it was not run.
- kicad-irdrop shares the current equally between a load's pads; boardlint's checks use the
  model's current per part. The comparison script (`tools/crosscheck_irdrop.py`) uses the equal
  split so the two can be compared. The checks themselves are not covered by it.
- padne, a finite-element solver, was not run: it needs a compiled build and directives added to
  the schematic. kicad-irdrop's README reports agreement with padne within 0.5 to 2.5 % on its
  own test board.
- Four boards, all from one small group of designers. No board with a defined stack-up, heavy
  copper, blind vias or arcs was in the set.

## Repeating it

The cases are in `docs/crosscheck/cases-*.json` and the figures above in `docs/crosscheck/results.json`.

```bash
python3 tools/crosscheck_irdrop.py /path/to/project docs/crosscheck/cases-dino-latest.json --inner-cu 0.035 --out mine.json
```

The reference side runs inside the KiCad 10 image, with kicad-irdrop and its dependencies (numpy,
scipy, shapely) on the Python path:

```bash
docker run --rm --network none -v /path/to/project:/data:ro -v "$PWD":/work -e PYTHONPATH=/work/kicad-irdrop/src:/work/deps kicad/kicad:10.0 python3 /work/boardlint/tools/crosscheck_kicad_irdrop.py /data/board.kicad_pcb /work/boardlint/docs/crosscheck/cases-dino-latest.json /work/reference.json 0.035 0.0125
```
