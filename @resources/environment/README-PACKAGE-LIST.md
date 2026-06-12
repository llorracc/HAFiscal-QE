# LaTeX Package List - Single Source of Truth (SST)

## Overview

The complete list of required LaTeX packages for HAFiscal is maintained in **`required-latex-packages.txt`** (SST). This file is used by:

- `Dockerfile` (Docker image builds)
- `reproduce/docker/setup.sh` (DevContainer setup)

## File Structure

### `required-latex-packages.txt`

Contains all required packages with annotations indicating collection membership:

- **`collection-latex`**: Packages included in `collection-latex` (installed via collection, not individually)
- **`scheme-minimal`**: Packages included in `scheme-minimal` (base TeX Live installation)
- **`standalone`**: Packages that must be installed individually via `tlmgr`

### `extract-standalone-packages.sh`

Helper script that extracts only standalone packages from `required-latex-packages.txt`. Used by build scripts to filter out packages already in collections.

## Usage

### Adding a New Package

1. **Add to `required-latex-packages.txt`** with appropriate annotation:

   ```bash
   newpackage # standalone
   ```

2. **Verify collection membership** (if unsure):

   ```bash
   docker exec <container> /usr/local/texlive/2025/bin/<arch>/tlmgr info newpackage | grep collection:
   ```

3. **Update annotation** if package is in `collection-latex` or `scheme-minimal`:

   ```bash
   newpackage # collection-latex
   ```

4. **Rebuild containers** - scripts automatically use the updated list

### Modifying Package List

- **Edit only** `required-latex-packages.txt`
- Changes automatically apply to:
  - Docker builds (next `docker build`)
  - DevContainer setup (next container rebuild)
  - All environments using the SST scripts

## Package Categories

### Collection-Latex Packages (28 packages)
Installed automatically when `collection-latex` is installed:

- `amsmath`, `babel`, `bigintcalc`, `bitset`, `bookmark`
- `geometry`, `graphics`, `hyperref`, `natbib`
- `etoolbox`, `ltxcmds`, `gettitlestring`, `intcalc`
- `kvdefinekeys`, `kvoptions`, `kvsetkeys`
- `refcount`, `rerunfilecheck`, `stringenc`, `uniquecounter`, `url`
- `hycolor`, `pdfescape`, `pdftexcmds`
- `tools` (provides `array.sty`, `enumerate.sty`, `verbatim.sty`)

### Scheme-Minimal Packages (2 packages)
Included in base TeX Live minimal scheme:

- `amsfonts`
- `iftex`

### Standalone Packages (70 packages)
Must be installed individually via `tlmgr install`:

- See `required-latex-packages.txt` for complete list

## Verification

### Test Package Extraction

```bash
./@resources/environment/extract-standalone-packages.sh | wc -l
# Should output: 70
```

### Verify Package List

```bash
# Check that all packages are accounted for
grep -E '^[^#]*#' @resources/environment/required-latex-packages.txt | \
  grep -v '^#' | wc -l
```

## Benefits

✅ **Single Source of Truth**: One file contains all package information  
✅ **Automatic Filtering**: Scripts only install packages not in collections  
✅ **Easy Maintenance**: Add/remove packages in one place  
✅ **Consistency**: Docker and DevContainer use identical package lists  
✅ **Documentation**: Collection membership clearly annotated  
