# Whitepaper figures

Regenerate:

```bash
uv run python scripts/render_whitepaper_figures.py
```

`fig3`–`fig5` are rendered with matplotlib (NeurIPS-style charts, Daytona palette). Conceptual figures (`fig1`, `fig2`, `fig6`) remain hand-authored SVG.

| File | Paper slot | Ledger |
| --- | --- | --- |
| `fig1-what-is-preserved.svg` | §3 | conceptual |
| `fig2-search-pipeline.svg` | §4.1 | conceptual |
| `fig3-headline-solve-rates.svg` | §6 | S5 (17/25 vs 6/25) |
| `fig4-warehouse-arms.svg` | §7 | S21 |
| `fig5-warehouse-tokens.svg` | §7 | S21 tokens |
| `fig6-failure-modes.svg` | §8 | S9–S14 qualitative |

Do not edit the SVGs by hand; change the renderer and re-run.
