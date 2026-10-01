"""Reglages specifiques a la plateforme (DPI Windows)."""

import sys

def configure_windows_dpi():
    """A appeler une seule fois au demarrage sur Windows pour un rendu net."""
    if sys.platform.startswith("win"):
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                from ctypes import windll
                windll.user32.SetProcessDPIAware()
            except Exception:
                pass
