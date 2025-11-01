# Benchmark Results

This directory contains individual benchmark results from reproduction runs.

## File Format

Results are stored as JSON files with names following the pattern:
```
YYYY-MM-DDTHH-MM-SSZ_mode_os-arch.json
```

Example:
```
2025-10-24T14-30-00Z_comp-min_darwin-arm64.json
```

## Viewing Results

```bash
# View latest benchmark
cat latest.json | jq .

# View all benchmarks
ls -lh *.json

# Compare two benchmarks
diff <(jq . benchmark1.json) <(jq . benchmark2.json)
```

## Gitignore

By default, individual benchmark JSON files are gitignored to prevent:
- Accumulation of large numbers of benchmark files
- User-specific system information in git history

To commit a benchmark (e.g., for reference data):
```bash
git add -f results/2025-10-24_comp-min_reference.json
```

## Reference Benchmarks

For inclusion in the repository, consider:
1. Representative hardware configurations
2. Clean, complete runs (no errors)
3. Significant milestones or optimizations
4. Cross-platform comparison data



