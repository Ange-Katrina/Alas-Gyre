"""Alas-Gyre Overlay Runtime bootstrap.

This module is loaded automatically by Python when the overlay directory is
prepended to PYTHONPATH. It hooks uvicorn.Config.load() and wraps the final
ASGI app with the Alas-Gyre API layer without modifying ALAS source files.
"""

import sys


def _install_uvicorn_hook():
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover - depends on host runtime
        print(f"[Alas-Gyre Overlay] uvicorn unavailable: {exc}")
        return

    original_load = getattr(uvicorn.Config, "load", None)
    if original_load is None or getattr(original_load, "_alas_gyre_patched", False):
        return

    def hooked_load(self):
        result = original_load(self)
        original_app = getattr(self, "loaded_app", None)
        if original_app is None or getattr(original_app, "_alas_gyre_overlay", False):
            return result

        try:
            from gyre_overlay_runtime import create_overlay_app

            self.loaded_app = create_overlay_app(original_app)
            self.loaded_app._alas_gyre_overlay = True
            print("[Alas-Gyre Overlay] Injected /api/gyre ASGI wrapper.")
        except Exception as exc:
            print(f"[Alas-Gyre Overlay] injection failed: {exc}")
        return result

    hooked_load._alas_gyre_patched = True
    uvicorn.Config.load = hooked_load
    print("[Alas-Gyre Overlay] Hooked uvicorn.Config.load().")


if not getattr(sys, "_alas_gyre_overlay_hooked", False):
    sys._alas_gyre_overlay_hooked = True
    _install_uvicorn_hook()
