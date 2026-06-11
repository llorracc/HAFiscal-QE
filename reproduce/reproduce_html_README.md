# HAFiscal HTML Generation

## `reproduce_html.sh`

**Purpose:** Generate HTML version of the paper for web viewing  

**When to use:** To create web-accessible version of the document  

**What it does:**

- Uses `make4ht` to convert LaTeX to HTML
- Outputs to `docs/` directory for GitHub Pages
- Handles bibliography and figures

**Usage:**

```bash
./reproduce/reproduce_html.sh
```

---

## Notes

This script is maintained separately from the main reproduction workflow. HTML generation is optional and not part of the standard replication process documented in the main README.

For the standard LaTeX PDF compilation workflow, use:

```bash
../reproduce.sh --docs main
```

---

**Last Updated:** 2025-10-30
