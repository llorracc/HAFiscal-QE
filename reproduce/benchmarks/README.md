# HAFiscal Reproduction Benchmarks

This directory contains benchmark data for reproduction runs, following industry-standard formats for performance tracking.

## Purpose

Track and document the time required to reproduce HAFiscal results across different:

- Hardware configurations (CPU, RAM, storage)
- Operating systems (macOS, Linux, Windows/WSL2)
- Reproduction modes (`--docs`, `--comp min`, `--comp full`)
- Environment types (UV vs Conda)

## Benchmark Format

Benchmarks are stored in **JSON format** following the [pytest-benchmark](https://pytest-benchmark.readthedocs.io/) and [GitHub Actions benchmark](https://github.com/benchmark-action/github-action-benchmark) conventions.

### JSON Schema

```json
{
  "benchmark_version": "1.0.0",
  "benchmark_id": "unique-id-timestamp",
  "timestamp": "ISO 8601 datetime",
  "reproduction_mode": "docs|comp-min|comp-all|all",
  "exit_status": 0,
  "duration_seconds": 12345.67,
  "system": {
    "os": "Darwin|Linux|Windows",
    "os_version": "24.4.0",
    "kernel": "Darwin Kernel Version...",
    "hostname": "machine-name",
    "cpu": {
      "model": "Intel(R) Core(TM) i9-9900K",
      "architecture": "x86_64|arm64",
      "cores_physical": 8,
      "cores_logical": 16,
      "frequency_mhz": 3600
    },
    "memory": {
      "total_gb": 32.0,
      "available_gb": 24.5
    },
    "disk": {
      "type": "SSD|HDD|NVMe",
      "free_gb": 500.0
    }
  },
  "environment": {
    "python_version": "3.9.18",
    "environment_type": "uv|conda",
    "virtual_env": "/path/to/.venv",
    "key_packages": {
      "econ-ark": "0.14.1",
      "numpy": "1.24.3",
      "scipy": "1.10.1"
    }
  },
  "git": {
    "commit": "abc123def456",
    "branch": "main",
    "dirty": false
  },
  "steps": [
    {
      "name": "Environment Setup",
      "duration_seconds": 1.23,
      "status": "success"
    },
    {
      "name": "Document Compilation",
      "duration_seconds": 234.56,
      "status": "success",
      "details": {
        "files_compiled": 2,
        "pages_generated": 45
      }
    },
    {
      "name": "Computational Results",
      "duration_seconds": 12000.0,
      "status": "success",
      "details": {
        "step_1": 1200.0,
        "step_2": 7560.0,
        "step_3": 3240.0
      }
    }
  ],
  "metadata": {
    "user": "username",
    "session_id": "unique-session-id",
    "ci": false,
    "notes": "Optional notes about this run"
  }
}
```

## Directory Structure

```
reproduce/benchmarks/
├── README.md                    # This file
├── BENCHMARKING_GUIDE.md        # Detailed guide for running benchmarks
├── schema.json                  # JSON schema for validation
├── benchmark.sh                 # Benchmark wrapper script
├── benchmark_results.sh         # View results in formatted table
├── capture_system_info.py       # System info capture utility
├── results/                     # Individual benchmark results
│   ├── docs_main_20251030-1515_00021s.json
│   ├── comp_full_20251027-1005_05650s.json
│   ├── envt_texlive_20251030-1724_00000s.json
│   └── latest.json -> [symlink to most recent]
├── summaries/                   # Human-readable summaries
│   ├── summary_2025-10.md
│   └── comparison.md
└── templates/                   # Report templates
    └── benchmark_report.md
```

## Usage

### Running a Benchmark

```bash
# Benchmark document reproduction
./reproduce/benchmarks/benchmark.sh --docs

# Benchmark minimal computation
./reproduce/benchmarks/benchmark.sh --comp min

# Benchmark full reproduction
./reproduce/benchmarks/benchmark.sh --comp full

# With custom notes
./reproduce/benchmarks/benchmark.sh --comp min --notes "Testing new optimization"
```

### Viewing Results

```bash
# View results in a formatted table (recommended)
./reproduce/benchmarks/benchmark_results.sh          # Show all benchmarks
./reproduce/benchmarks/benchmark_results.sh docs     # Show only document compilations
./reproduce/benchmarks/benchmark_results.sh comp     # Show only computational runs
./reproduce/benchmarks/benchmark_results.sh envt     # Show only environment tests
./reproduce/benchmarks/benchmark_results.sh data     # Show only data processing

# View latest benchmark (raw JSON)
cat reproduce/benchmarks/results/latest.json | jq .

# View specific benchmark fields
cat reproduce/benchmarks/results/latest.json | jq '.duration_seconds'
cat reproduce/benchmarks/results/latest.json | jq '.system.cpu'

# View all benchmarks (raw files)
ls -lh reproduce/benchmarks/results/
```

## Benchmark Contributions

When contributing benchmark results:

1. **Run on clean system**: Ensure no other intensive processes are running
2. **Document hardware**: Include detailed CPU/RAM/storage specs
3. **Note any deviations**: Document any non-standard configuration
4. **Commit results**: Add JSON file to `results/` directory
5. **Update summary**: Add entry to monthly summary if significant

### Example Contribution

```bash
# Run benchmark
./reproduce/benchmarks/benchmark.sh --comp min --notes "MacBook Pro M1 Max 2021"

# Results automatically saved to:
# reproduce/benchmarks/results/2025-10-24T14-30-00Z_comp-min_macos-arm64.json

# Commit
git add reproduce/benchmarks/results/2025-10-24T14-30-00Z_comp-min_macos-arm64.json
git commit -m "Add benchmark: comp-min on M1 Max"
```

## Reference Benchmarks

### Expected Times (as of 2025-10-24)

| Reproduction Mode | Hardware Reference | Expected Duration |
|-------------------|-------------------|-------------------|
| `--docs` | High-end 2025 laptop | 5-10 minutes |
| `--comp min` | High-end 2025 laptop | ~1 hour |
| `--comp full` | High-end 2025 laptop | 4-5 days on a high-end 2025 laptop |

**Reference Hardware**:

- CPU: 8+ cores, 3.0+ GHz
- RAM: 32 GB
- Storage: NVMe SSD
- OS: macOS/Linux/WSL2

## Benchmark Analysis

The benchmark data can be used for:

1. **Performance regression detection**: Compare runs over time
2. **Hardware recommendations**: Guide users on expected performance
3. **Optimization validation**: Measure impact of code improvements
4. **Cross-platform comparison**: Compare macOS vs Linux vs WSL2
5. **Resource planning**: Estimate cloud computing costs

## Tools for Analysis

```bash
# Compare two benchmarks
./reproduce/benchmarks/compare.py results/benchmark1.json results/benchmark2.json

# Generate statistics
./reproduce/benchmarks/stats.py results/

# Plot duration trends
./reproduce/benchmarks/plot_trends.py results/ --output trends.png
```

## CI/CD Integration

For automated benchmarking in CI:

```yaml
- name: Run Benchmark
  run: |
    ./reproduce/benchmarks/benchmark.sh --comp min
    
- name: Compare to Baseline
  uses: benchmark-action/github-action-benchmark@v1
  with:
    tool: 'customBiggerIsBetter'
    output-file-path: reproduce/benchmarks/results/latest.json
```

## Questions or Issues?

For questions about benchmarking:

- See [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md)
- Open an issue with label `benchmarking`
- Contact maintainers

---

**Last Updated**: 2025-10-24  
**Benchmark Format Version**: 1.0.0
