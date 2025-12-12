# Using Docker

This guide explains how to build and use the Docker container.

## Prerequisites

- **Docker**: Install Docker Desktop or Docker Engine. See [Docker installation guide](https://docs.docker.com/get-docker/)
- **Git**: To clone the repository

## Build and Test

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd <repository-name>
   ```

2. **Set repository-specific names (prevents conflicts between repos):**

   ```bash
   # Automatically detects repository name from current directory
   REPO_NAME=$(basename $(pwd) | sed 's/HAFiscal-//' | tr '[:upper:]' '[:lower:]')
   ```

3. **Build the Docker image:**

   ```bash
   docker build -t hafiscal-${REPO_NAME}:latest .
   ```

   **Note:** First build takes 15-20 minutes as it installs TeX Live 2025 and sets up the Python environment.

4. **Start the container:**

   ```bash
   docker run -d --name hafiscal-${REPO_NAME}-container \
     -p 8888:8888 -p 8866:8866 \
     hafiscal-${REPO_NAME}:latest tail -f /dev/null
   ```

5. **Connect to container and run test:**

   ```bash
   docker exec -it hafiscal-${REPO_NAME}-container bash -c "cd /workspace && ./reproduce.sh --envt"
   ```

   Or connect interactively:

   ```bash
   docker exec -it hafiscal-${REPO_NAME}-container bash
   ./reproduce.sh --help
   ```

**Note:** The repository name is automatically detected from the current directory. This ensures unique image and container names, preventing conflicts.

---

**Last Updated:** December 3, 2025
