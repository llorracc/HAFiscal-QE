# Benchmark Results

This directory contains benchmark results from reproduction runs, organized into two subdirectories:

## Directory Structure

```
results/
├── auto/           # Temporary benchmark runs (gitignored)
├── saved/          # Hand-picked important results (tracked in git)
└── latest.json     # Symlink to most recent run (convenience)
```

### `auto/` - Automatic Benchmark Results

All benchmark runs are automatically saved here. These files are **gitignored** to prevent:

- Accumulation of large numbers of temporary benchmark files
- User-specific system information in git history
- Repository bloat from repeated runs

**Usage:**

```bash
# Benchmarks automatically save to auto/
./reproduce/benchmarks/benchmark.sh --docs main

# View latest
cat results/latest.json | jq .
cat results/auto/latest.json | jq .
```

### `saved/` - Curated Benchmark Results

Hand-picked important benchmark results. These files are **tracked in git** for:

- Reference hardware configurations
- Performance regression testing
- Milestone benchmarks
- Cross-platform comparison data

**To preserve a benchmark:**

```bash
# Copy from auto/ to saved/ with a descriptive name
cp auto/docs_main_20251109-1203_000072s.json saved/baseline_m1_max.json

# Or rename for clarity
cp auto/all_full_20251101-0043_525235s.json saved/full_run_v1.0.json

# Commit it
git add saved/baseline_m1_max.json
git commit -m "Add baseline benchmark: M1 Max"
```

## File Format

Results are stored as JSON files with system information and reproduction metadata:

**Auto-generated names:**

```
SCOPE_YYYYMMDD-HHMMh_DDDDDDs.json
```

Example: `docs_main_20251109-1203_000072s.json`

**Saved names (your choice):**

```
descriptive_name.json
```

Examples:

- `baseline_m1_max.json`
- `full_run_v1.0_release.json`
- `reference_intel_i9.json`

## Viewing Results

```bash
# View latest benchmark
cat results/latest.json | jq .

# View all auto benchmarks
ls -lh auto/

# View saved benchmarks
ls -lh saved/

# Use the display script (shows both auto/ and saved/)
./benchmarks/benchmark_results.sh

# Compare two benchmarks
diff <(jq . auto/benchmark1.json) <(jq . saved/baseline.json)
```

## Git Status

```bash
# Check which files are tracked
git status results/

# Saved results are tracked
git ls-files results/saved/

# Auto results are ignored
git check-ignore results/auto/*.json
```

## Criteria for Saving Benchmarks

Consider saving a benchmark to `saved/` if it represents:

1. **Representative hardware** - Common configurations (M1, M2, Intel i7/i9, etc.)
2. **Clean complete runs** - No errors, full reproduction
3. **Milestones** - Major version releases, optimizations
4. **Regression testing** - Baseline performance for comparison
5. **Cross-platform data** - macOS vs Linux, ARM vs x86
6. **Documentation** - Examples for README/guides

## Example Workflow

```bash
# Run a benchmark
./reproduce/benchmarks/benchmark.sh --docs main

# Check the result
./reproduce/benchmarks/benchmark_results.sh

# If it's worth keeping, preserve it
cp auto/docs_main_20251109-1203_000072s.json saved/baseline_docs_2025-11.json

# Commit it
git add saved/baseline_docs_2025-11.json
git commit -m "Add baseline doc compilation benchmark (Nov 2025)"
```

## Notes

- The `.gitkeep` files in `auto/` and `saved/` ensure directories are preserved even when empty
- The `latest.json` symlink in the root always points to the most recent run for convenience
- Saved benchmarks can be deleted/updated like any other tracked file
- Old auto benchmarks can be cleaned up anytime: `rm auto/*_20241*.json`
