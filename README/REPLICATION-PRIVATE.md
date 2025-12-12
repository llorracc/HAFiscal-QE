# Repository Architecture Notice (PRIVATE - Latest Only)

**This section explains the repository architecture and is only relevant for the HAFiscal-Latest repository.**

## ℹ️ Repository Architecture Notice

**This is the Single Source of Truth (SST) repository.**

`HAFiscal-Latest` is the development repository containing all LaTeX and code artifacts. This is the authoritative source for all content.

**Change Flow:**

```
HAFiscal-Latest (SST) → HAFiscal-Public → HAFiscal-QE
```

**Other Repositories:**

- **HAFiscal-Public**: Public release version (generated from Latest)
- **HAFiscal-QE**: Journal submission version (generated from Public)
- **econ-ark/HAFiscal**: Fork of Public (contributions should go to Latest/Public)

All changes to LaTeX content, code, figures, and tables should be made in this repository. Changes will automatically flow to Public and QE through the build scripts.
