# --- canvas/handlers/overlay.py ---
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageGrab
import logging
import os

try: LANCZOS_RESAMPLE = Image.Resampling.LANCZOS
except AttributeError: LANCZOS_RESAMPLE = Image.LANCZOS;

class OverlayHandler:
    def __init__(self, canvas_view):
        self.view = canvas_view

    def paste_from_clipboard(self):
        """Grabs image, resets zoom, adds overlay at appropriate origin."""
        view = self.view
        try:
            logging.info("Overlay Paste: Attempting...")
            if hasattr(view, 'reset_zoom'): view.reset_zoom()

            image = ImageGrab.grabclipboard()
            if isinstance(image, Image.Image):
                view.pasted_overlay_pil_image = image.convert("RGBA")
                logging.info(f"Overlay Paste: Stored PIL size {view.pasted_overlay_pil_image.size}.")

                if view.pasted_overlay_item_id and view.canvas.find_withtag(view.pasted_overlay_item_id): view.canvas.delete(view.pasted_overlay_item_id)
                view.pasted_overlay_item_id = None; view.pasted_overlay_tk_image = None

                view.pasted_overlay_tk_image = ImageTk.PhotoImage(view.pasted_overlay_pil_image)

                # *** Determine Paste Position ***
                if view.last_capture_origin is not None:
                     initial_x, initial_y = view.last_capture_origin
                     logging.info(f"Overlay Paste: Using last capture origin ({initial_x},{initial_y}) for placement.")
                     # Clear origin after use for paste so next non-layout paste is at 0,0
                     view.last_capture_origin = None
                else:
                     initial_x, initial_y = 0, 0 # Default to 0,0 if no capture origin
                     logging.info(f"Overlay Paste: Using standard origin (0,0) for placement.")

                # Store the placement coords as the CURRENT offset
                view.pasted_overlay_offset = (initial_x, initial_y)

                view.pasted_overlay_item_id = view.canvas.create_image(initial_x, initial_y, anchor="nw", image=view.pasted_overlay_tk_image, tags=("draggable", "pasted_overlay"))

                # --- Overlay stacking order ---
                overlay_behind = False
                if hasattr(view, 'app') and hasattr(view.app, 'layer_behind_mode'):
                    overlay_behind = view.app.layer_behind_mode.get()
                if overlay_behind:
                    # Lower overlay below all draggable items
                    view.canvas.tag_lower(view.pasted_overlay_item_id, "draggable")
                else:
                    # Raise overlay above all
                    view.canvas.tag_raise(view.pasted_overlay_item_id)
                # --- End stacking order ---

                logging.info(f"Overlay Paste: Displayed ID: {view.pasted_overlay_item_id} at ({initial_x},{initial_y}).")
                messagebox.showinfo("Paste Successful", "Image pasted as overlay.\nDrag to align.")

            elif image: logging.warning(f"Clipboard not image: {type(image)}"); messagebox.showwarning("Warning","Clipboard not image."); self._clear_overlay_state()
            else: logging.warning("No image in clipboard"); messagebox.showwarning("Warning","No image found."); self._clear_overlay_state()
        except Exception as e:
            logging.error(f"Overlay Paste Error: {e}", exc_info=True); messagebox.showerror("Error", f"Paste failed.\n{e}");
            self._clear_overlay_state()

    def _clear_overlay_state(self):
        view = self.view; view.pasted_overlay_pil_image = None
        if view.pasted_overlay_item_id and view.canvas.find_withtag(view.pasted_overlay_item_id): view.canvas.delete(view.pasted_overlay_item_id)
        view.pasted_overlay_item_id = None; view.pasted_overlay_tk_image = None
        view.pasted_overlay_offset = (0, 0); view.last_capture_origin = None # Clear origin
        logging.debug("Overlay state cleared.")