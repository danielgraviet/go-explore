# Whitepaper figures

| File | Paper slot | Source |
| --- | --- | --- |
| `fig1-what-is-preserved` | §3 | Designer SVG (Daytona palette) |
| `fig2-search-pipeline` | §4.1 | Designer SVG (Daytona palette) |
| `fig3-headline-solve-rates` | §6 | Matplotlib, S5 (17/25 vs 6/25) |
| `fig4-warehouse-arms` | §7 | Matplotlib, S21 |
| `fig5-warehouse-tokens` | §7 | Matplotlib, S21 tokens |
| `fig6-failure-modes` | §8 | Designer SVG (Daytona palette) |

Formats:

```text
figures/figN-....svg   # source of truth (designer or matplotlib)
figures/figN-....pdf   # used by LaTeX / Overleaf (vector)
figures/figN-....png   # blog / slides
```

`pdflatex` cannot include SVG directly, so LaTeX loads the PDF companions.
Those PDFs are vector conversions of the SVGs — not raster PNGs — so figures
stay sharp at any zoom.

## Regenerating PDF companions from designer SVGs

Requires Homebrew `cairo`. Do **not** use `svglib` — it mangles Figma exports
(e.g. solid-fills panel glyphs).

```bash
cd docs/whitepaper/figures
export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix cairo)/lib:$(brew --prefix)/lib"
uv run --with cairosvg python - <<'PY'
import cairosvg
for name in [
    "fig1-what-is-preserved",
    "fig2-search-pipeline",
    "fig6-failure-modes",
]:
    cairosvg.svg2pdf(url=f"{name}.svg", write_to=f"{name}.pdf")
    print("wrote", name + ".pdf")
PY
```

## Regenerating chart figures

```bash
uv run python scripts/render_whitepaper_figures.py
```

That writes SVG for `fig3`–`fig5`. Also emit PDF (and optional PNG) from
matplotlib before compiling LaTeX; do not overwrite designer `fig1`/`fig2`/`fig6`.
