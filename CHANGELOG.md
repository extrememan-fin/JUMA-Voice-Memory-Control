# Changelog

All notable changes to **JUMA Voice Memory Controller** will be documented in this file.

## [1.0.0] - 2025-10-26
### Added
- Initial public release.
- Cross‑platform GUI (macOS / Windows / Linux) using **CustomTkinter**.
- RS‑232 serial control for JUMA transceivers via **pyserial**.
- Core functions: **MIC record**, **RX record**, **Play**, **Transmit**, **Stop**.
- Numeric memory keys **0–9** with mouse & keyboard hotkeys.
- Live **Status** and **Command** feedback line.
- **Light/Dark** theme toggle with preference memory.
- Compact, balanced layout; color‑coded function buttons.
- Example build scripts for macOS (.app + DMG) and Windows (.exe).

### Notes
- Python **3.9+** supported (tested up to 3.14).
- macOS: first‑run Gatekeeper prompts may require manual approval or `xattr` removal (see README).
- Serial port naming differs by OS (e.g., `/dev/cu.*` on macOS, `COM*` on Windows).

### Credits
- Developed by **OH2DDG**.  
- Technical assistance by **OH7SV**.
