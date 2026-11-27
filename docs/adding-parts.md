# Adding a part model

boardlint knows a part through a *part model*: one YAML file of facts from its datasheet (supply
range, what each pin is for, what the datasheet says must be connected to it). A part with no
model is still checked, but only by rules that work from pin names, so a clean report means less.
When a report says parts have no model, this page is what to do about it.

An LLM that can read a PDF does most of the work. A person then checks the result against the
datasheet. Allow about ten minutes for a simple part.

## 1. See which parts need one

```bash
boardlint parts path/to/project
```

Parts with `-` in the model column have none. Integrated circuits, regulators, transistors and
connectors with a protocol (USB) matter most. Plain resistors, capacitors and headers need none.

## 2. Get the datasheet

Use the manufacturer's PDF for the exact part number on the board. If the schematic has a
`Datasheet` field, start there.

## 3. Ask an LLM to write the model

Give it three things:

- the datasheet PDF;
- the prompt in [`tools/extract_prompt.md`](../tools/extract_prompt.md) and the schema in
  [`part-model-schema.md`](part-model-schema.md);
- one existing model of the same kind as an example, from `boardlint/library/parts/`:

| Kind of part | Example to give |
|---|---|
| Linear regulator | `rt9080-33.yaml` |
| I2C sensor | `lis2dh12.yaml` |
| SPI converter or memory | `mcp3208.yaml`, `w25q32jv.yaml` |
| Microcontroller or module | `rp2350b.yaml`, `esp32-s3-mini-1.yaml` |
| Logic gate | `74ahct1g125.yaml` |
| MOSFET | `ao3401a.yaml` |
| Op-amp | `mcp6002.yaml` |
| Fuse, TVS diode | `polyfuse-1812-1.1a.yaml`, `smaj15a.yaml` |

Also tell it the pin names and the value exactly as they appear on your schematic, because the
model has to match them. `boardlint parts` prints the value.

With Claude Code in a checkout of this repository, this is enough:

> Write a boardlint part model for U3 (MCP3208) in path/to/project. Follow tools/extract_prompt.md
> and docs/part-model-schema.md, use mcp3208.yaml as the style example, and read the datasheet at
> <URL>. Put it in my_parts/. Then run `boardlint parts` to confirm it matches.

## 4. Check it

Read the YAML against the datasheet. The things that go wrong most:

- a number from the "typical" column used as a limit;
- the absolute-maximum table mixed up with the operating range;
- a pinout taken from the wrong package or variant;
- `verified: true` on something the model filled in from memory. The prompt forbids this, and
  `provenance.notes` should name a page or table for every number.

## 5. Use it

For one project, keep the file in a folder beside it:

```bash
boardlint check path/to/project --parts-dir my_parts/
```

Run `boardlint parts path/to/project --parts-dir my_parts/` first: the part should now show the
model's id. If it still shows `-`, the `match:` pattern does not fit the part's value.

To share it, add the file to `boardlint/library/parts/` and open a pull request. `python3 -m
pytest -q tests/test_units.py` loads every model in the library and fails on one that does not parse.

## Limits, at the time of writing

- There is no command that checks a model against the schema. A misspelt field name is ignored
  without a message.
- A model matches on the value alone, not on value and kind of part together, so keep the pattern tight.
- `boardlint model new <datasheet.pdf>`, which would run steps 3 and 4, is planned and not built.
