# Using Docker with HAFiscal-QE

## Quick Start (Pre-built Image - Recommended)

The easiest way to use this repository is with the pre-built Docker image:

```bash
# Pull the image from DockerHub
docker pull llorracc/hafiscal-qe:latest

# Run interactively
docker run -it llorracc/hafiscal-qe:latest

# Inside container
cd /workspace
./reproduce.sh --docs       # Build paper (30 seconds)
./reproduce.sh --comp min   # Quick validation (1 hour)
./reproduce.sh --comp full  # Full replication (4-5 days)
```

**Image Details**:
- **DockerHub**: https://hub.docker.com/r/llorracc/hafiscal-qe
- **Size**: 3.2 GB
- **Includes**: TeX Live 2025, Python 3.11, all dependencies
- **Verified**: QE compliance tested

## Building from Source (Advanced)

If you need to customize the environment:

```bash
git clone https://github.com/${QE_GITHUB_ORG:-llorracc}/HAFiscal-QE
cd HAFiscal-QE

docker build -t llorracc/hafiscal-qe:latest .
```

**Build time**: 15-20 minutes (installs TeX Live + Python environment)

## Prerequisites

- **Docker**: Install Docker Desktop or Docker Engine
  - [Docker installation guide](https://docs.docker.com/get-docker/)
- **Git**: For cloning repository

---

**Last Updated**: December 15, 2025
