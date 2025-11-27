# HAFiscal Benchmarking Guide

## Overview

The HAFiscal benchmarking system follows industry-standard practices for capturing and reporting reproduction run times across different hardware, operating systems, and configurations.

## Quick Start

### Running a Benchmark

```bash
# Benchmark document compilation
./reproduce/benchmarks/benchmark.sh --docs

# Benchmark minimal computation (~1 hour)
./reproduce/benchmarks/benchmark.sh --comp min

# Benchmark full reproduction (4-5 days)
./reproduce/benchmarks/benchmark.sh --comp full

# With notes
./reproduce/benchmarks/benchmark.sh --comp min --notes "Testing M1 Max performance"
```

### Viewing Results

```bash
# View latest benchmark
cat reproduce/benchmarks/results/latest.json | jq .

# View system info from latest
cat reproduce/benchmarks/results/latest.json | jq '.system'

# Check duration
cat reproduce/benchmarks/results/latest.json | jq '.duration_seconds'
```

## What Gets Captured

### System Information
- **OS**: Operating system name, version, kernel
- **CPU**: Model, architecture (x86_64/arm64), core count, frequency
- **Memory**: Total RAM, available RAM
- **Disk**: Type (SSD/HDD/NVMe), free space
- **Hostname**: Machine name (can be anonymized)

### Environment
- **Python Version**: e.g., 3.9.18
- **Environment Type**: uv, conda, venv
- **Virtual Environment Path**: Location of .venv or conda env
- **Key Packages**: Versions of econ-ark, numpy, scipy, pandas, etc.

### Git State
- **Commit**: Git commit hash
- **Branch**: Active branch name
- **Dirty**: Whether there are uncommitted changes

### Timing
- **Start/End Timestamps**: ISO 8601 format (UTC)
- **Duration**: Total seconds + formatted time (HH:MM:SS)
- **Exit Status**: Success (0) or error code
- **Step Timings** (future enhancement): Individual step durations

### Metadata
- **User**: Username (for tracking who ran benchmark)
- **Session ID**: Unique process ID
- **CI Flag**: Whether run in CI/CD environment
- **Notes**: Optional user-provided notes

## Data Format

Benchmarks are stored as JSON following these industry standards:
- [pytest-benchmark](https://pytest-benchmark.readthedocs.io/) format
- [GitHub Actions benchmark](https://github.com/benchmark-action/github-action-benchmark) conventions
- Cross-platform compatibility (macOS, Linux, Windows/WSL2)

Example structure:
```json
{
  "benchmark_version": "1.0.0",
  "benchmark_id": "2025-10-24T14-30-00Z_comp-min_darwin-arm64",
  "timestamp": "2025-10-24T14:30:00Z",
  "reproduction_mode": "comp-min",
  "exit_status": 0,
  "duration_seconds": 3600,
  "system": { ... },
  "environment": { ... },
  "git": { ... },
  "metadata": { ... }
}
```

## Storage Location

```
reproduce/benchmarks/
├── README.md                    # Overview and documentation
├── BENCHMARKING_GUIDE.md        # This file
├── schema.json                  # JSON schema for validation
├── benchmark.sh                 # Main benchmarking wrapper
├── capture_system_info.py       # System info capture utility
└── results/                     # Benchmark results (gitignored by default)
    ├── README.md
    ├── .gitignore
    ├── latest.json -> 2025-10-24...json  # Symlink to latest
    └── 2025-10-24T14-30-00Z_comp-min_darwin-arm64.json
```

## Privacy and Data Sharing

### What's Safe to Share
- OS, CPU, memory specs
- Duration and performance metrics
- Python and package versions
- Git commit (public repo)

### What to Redact
- Hostname (if it contains personal info)
- Username (if privacy is a concern)
- Virtual environment paths (may contain usernames)
- Any custom notes with sensitive info

### Sharing Benchmarks

```bash
# Create anonymized copy
jq 'del(.system.hostname, .metadata.user, .environment.virtual_env)' \
   results/benchmark.json > benchmark_anonymous.json

# Commit reference benchmark
git add -f reproduce/benchmarks/results/2025-10-24_reference_m1max.json
git commit -m "Add reference benchmark: M1 Max 2021"
```

## Use Cases

### 1. Performance Tracking
Track reproduction time over different code versions:
```bash
# Before optimization
./reproduce/benchmarks/benchmark.sh --comp min --notes "Before optimization"

# After optimization
./reproduce/benchmarks/benchmark.sh --comp min --notes "After optimization"

# Compare
jq '.duration_seconds' results/*.json
```

### 2. Hardware Comparison
Compare performance across different machines:
```bash
# On laptop
./reproduce/benchmarks/benchmark.sh --comp min --notes "MacBook Pro M1 2021"

# On desktop
./reproduce/benchmarks/benchmark.sh --comp min --notes "AMD Ryzen 9 5900X"

# On cloud
./reproduce/benchmarks/benchmark.sh --comp min --notes "AWS c6i.8xlarge"
```

### 3. Environment Comparison
Compare UV vs Conda:
```bash
# With UV
source .venv/bin/activate
./reproduce/benchmarks/benchmark.sh --docs --notes "UV environment"

# With Conda
conda activate hafiscal
./reproduce/benchmarks/benchmark.sh --docs --notes "Conda environment"
```

### 4. CI/CD Integration
Automated performance regression detection:
```yaml
- name: Run Benchmark
  run: ./reproduce/benchmarks/benchmark.sh --comp min
  
- name: Upload Results
  uses: actions/upload-artifact@v3
  with:
    name: benchmark-results
    path: reproduce/benchmarks/results/latest.json
```

## Best Practices

### Running Benchmarks

1. **Close other applications**: Ensure no other intensive processes
2. **Use consistent power settings**: Avoid power-saving modes
3. **Let system stabilize**: Wait a few minutes after boot
4. **Monitor resources**: Check that CPU/RAM aren't constrained
5. **Document configuration**: Use --notes for any special setup

### Recording Benchmarks

1. **Use descriptive notes**: Include hardware details, purpose
2. **Run multiple times**: Verify consistency (if time permits)
3. **Document anomalies**: Note any interruptions or issues
4. **Keep git clean**: Commit code changes separately from benchmarks
5. **Share selectively**: Commit reference benchmarks, gitignore routine runs

### Interpreting Results

1. **Expect variance**: ±10-20% is normal for long-running tasks
2. **Consider context**: Background processes, system load
3. **Compare apples-to-apples**: Same OS, similar hardware
4. **Look at trends**: Multiple runs over time, not single comparisons
5. **Account for randomness**: Optimization routines may vary slightly

## Troubleshooting

### Benchmark Script Fails

**Problem**: `benchmark.sh` exits with error

**Solution**:
```bash
# Check if Python 3 is available
python3 --version

# Check if jq is installed (needed for JSON)
which jq || brew install jq  # macOS
which jq || sudo apt install jq  # Linux

# Run with bash explicitly
bash reproduce/benchmarks/benchmark.sh --docs
```

### System Info Incomplete

**Problem**: Some system fields show "unknown"

**Cause**: Platform-specific commands not available

**Impact**: Non-critical, benchmark still valid

**Solution**: Install system utilities (lscpu, sysctl, etc.)

### Duration Seems Wrong

**Problem**: Very short or long duration

**Possible causes**:
- Cached results (for documents)
- System suspended/hibernated
- Interrupted and restarted
- Missing dependencies caused early exit

**Solution**: Check exit_status in JSON, run with clean state

## Advanced Usage

### Custom Steps Timing (Future)

For advanced timing of individual steps, modify the reproduction
scripts to emit timing markers that can be parsed.

### Continuous Benchmarking

Set up automated benchmarking on each commit:
```bash
# .github/workflows/benchmark.yml
on: [push]
jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup environment
        run: ./reproduce/reproduce_environment_comp_uv.sh
      - name: Run benchmark
        run: ./reproduce/benchmarks/benchmark.sh --docs
      - name: Store results
        uses: benchmark-action/github-action-benchmark@v1
```

### Analysis Scripts

Create custom analysis tools:
```python
#!/usr/bin/env python3
import json
import glob

# Load all benchmarks
benchmarks = []
for file in glob.glob("reproduce/benchmarks/results/*.json"):
    with open(file) as f:
        benchmarks.append(json.load(f))

# Analyze
for b in sorted(benchmarks, key=lambda x: x['duration_seconds']):
    mode = b['reproduction_mode']
    duration = b['duration_seconds'] / 3600  # hours
    cpu = b['system']['cpu']['model']
    print(f"{mode:15} {duration:6.2f}h  {cpu}")
```

## Contributing Benchmarks

We welcome benchmark contributions, especially for:
- Different CPU architectures (Intel, AMD, ARM)
- Different operating systems (macOS, Ubuntu, Fedora, WSL2)
- Different hardware tiers (laptop, workstation, HPC)
- CI/CD environments (GitHub Actions, GitLab CI)

See [README.md](README.md) for contribution guidelines.

## References

- [pytest-benchmark Documentation](https://pytest-benchmark.readthedocs.io/)
- [GitHub Actions Benchmark Action](https://github.com/benchmark-action/github-action-benchmark)
- [Hyperfine Benchmarking Tool](https://github.com/sharkdp/hyperfine)
- [Best Practices for Benchmarking](https://pyperf.readthedocs.io/en/latest/api.html)

---

**Last Updated**: 2025-10-24  
**Benchmark Format Version**: 1.0.0



