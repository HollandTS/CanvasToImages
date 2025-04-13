# --- canvas/utils.py ---
import tkinter as tk
from tkinter import messagebox
from PIL import ImageGrab
import logging

def is_above_canvas(canvas_widget, event):
    """Checks if the global mouse event coordinates are over the canvas widget."""
    try:
        x0=canvas_widget.winfo_rootx(); y0=canvas_widget.winfo_rooty()
        x1=x0+canvas_widget.winfo_width(); y1=y0+canvas_widget.winfo_height()
        return x0 <= event.x_root <= x1 and y0 <= event.y_root <= y1
    except Exception as e: logging.error(f"Error checking if above canvas: {e}", exc_info=True); return False

def save_canvas_image(canvas_widget, file_path):
    """Saves the current visual state of the canvas via ImageGrab."""
    try:
        logging.info(f"Saving canvas layout to {file_path}"); canvas_widget.update_idletasks()
        x0=canvas_widget.winfo_rootx(); y0=canvas_widget.winfo_rooty()
        x1=x0+canvas_widget.winfo_width(); y1=y0+canvas_widget.winfo_height()
        img=ImageGrab.grab(bbox=(x0,y0,x1,y1)); img.save(file_path)
        logging.info(f"Canvas saved: {file_path}"); messagebox.showinfo("Save OK", f"Saved:\n{file_path}")
    except Exception as e: logging.error(f"Save canvas error: {e}", exc_info=True); messagebox.showerror("Error", f"Save failed.\n{e}")