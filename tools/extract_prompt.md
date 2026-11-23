# Datasheet to part model: extraction prompt

Use this with an LLM that can read the PDF (or `pdftotext -layout` output). The result is reviewed by
a person and committed to `boardlint/library/parts/`.

> You are extracting a machine-readable part model from a component datasheet for a PCB design
> checker. Follow `docs/part-model-schema.md` exactly; output one YAML document.
>
> Rules:
> 1. Only write a number you can point to in the datasheet. Put the page or table in
>    `provenance.notes`. If the datasheet does not state something, leave the field out. Never fill a
>    gap from general knowledge without setting `provenance.verified: false` and saying which fields.
> 2. Use recommended-operating limits for `vmin`/`vmax` and the absolute-maximum table for `abs_max`.
> 3. Pin names exactly as the datasheet's pin table prints them; add every pin that has a required
>    external connection (`require`), a protocol role, or a limit different from the `io` defaults.
> 4. Turn every "must", "should be connected", "requires a ... capacitor" sentence of the pin
>    description and application sections into a `require` or `decoupling` entry.
> 5. I2C addresses as 7-bit hex, with the strap mapping. Identification registers into `sim.params`.
> 6. Search the manufacturer's errata sheet and the usual forums for known board-level pitfalls of
>    this part; add them under `errata` with a source URL. Do not invent any.
