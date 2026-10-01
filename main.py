"""Point d'entree de l'application Aide au Layout et Stringing PV."""

import sys
import tkinter as tk
import os

from platform_setup import configure_windows_dpi
from app import PVLayoutRibbonApp

if sys.platform.startswith("win"):
    configure_windows_dpi()

if __name__ == "__main__":
    root = tk.Tk()
    app = PVLayoutRibbonApp(root)
    root.mainloop()
