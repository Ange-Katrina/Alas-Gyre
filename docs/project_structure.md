# Alas-Gyre Project Structure

This document is a short maintenance note for contributors. End-user setup is documented in `README.md` and `README.zh-cn.md`.

```text
Alas-Gyre_Fresh/
├─ alas_gyre/              # Core application package
│  ├─ api/                 # Overlay, ALAS API, and runtime update helpers
│  ├─ core/                # Config, paths, status, and version helpers
│  └─ services/            # App update service helpers
├─ ui/                     # PySide6 desktop UI
│  ├─ assets/              # Icons and UI assets
│  └─ widgets/             # Shared custom widgets
├─ overlay/                # Runtime files injected by the Gyre launcher
├─ resources/              # Launcher templates and runtime updater source
├─ tools/                  # Development utilities
├─ docs/                   # README screenshots and contributor notes
├─ main.py                 # Desktop client entry point
├─ Alas-Gyre.spec          # Windows PyInstaller build spec
└─ config.example.json     # Example configuration
```

## Notes

- Generated/runtime files such as `config.json`, `gyre_runtime/`, `build/`, and `dist/` should not be committed.
- Overlay runtime files are mirrored into generated launchers by `alas_gyre.api.overlay_launcher`.
- `tools/mock_server.py` can be used for local UI/API smoke testing:

```bash
python tools/mock_server.py
```
