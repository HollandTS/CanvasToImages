# --- canvas/handlers/tile.py ---
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import logging

class TileHandler:
    def __init__(self, canvas_view):
        self.view = canvas_view

    def add_tile(self, image, filename, x=0, y=0):
        """Adds a tile image to the canvas."""
        view = self.view
        try:
            logging.info(f"Tile Add: {filename} at ({x},{y})")
            if filename in view.images:
                 logging.warning(f"Tile Add: Replacing: {filename}")
                 existing_id = view.images[filename]['id']
                 if view.canvas.find_withtag(existing_id): view.canvas.delete(existing_id)

            display_pil = image.copy()
            # Use background handler to apply transparency
            if view.background_color:
                display_pil = view.bg_handler.apply_transparency(display_pil, view.background_color)

            tk_image = ImageTk.PhotoImage(display_pil)
            view.tk_images.append(tk_image) # Add to list for tiles

            image_id = view.canvas.create_image(x, y, anchor="nw", image=tk_image, tags=("draggable", filename))
            view.images[filename] = {"id": image_id, "image": image, "original_image": image.copy(), "filename": filename, "x": x, "y": y}

            if view.pasted_overlay_item_id and view.canvas.find_withtag(view.pasted_overlay_item_id):
                 view.canvas.tag_raise(image_id, view.pasted_overlay_item_id) # Place under overlay

            logging.info(f"Tile Add: OK (ID: {image_id}).")

        except Exception as e: logging.error(f"Tile Add Error ({filename}): {e}", exc_info=True)

    def remove_tile(self, filename):
        """Removes a specific tile instance from the canvas."""
        view = self.view
        try:
            logging.info(f"Tile Remove: {filename}")
            if filename in view.images:
                item_id = view.images[filename]["id"]
                if view.canvas.find_withtag(item_id): view.canvas.delete(item_id)
                # TODO: Remove corresponding tk_image from view.tk_images
                del view.images[filename]
                logging.info(f"Tile Remove: OK.")
                # Update external listbox via app reference
                if hasattr(view.app, 'remove_from_filelist'):
                    view.app.remove_from_filelist(filename)
            else: logging.warning(f"Tile Remove: Not found: {filename}")
        except Exception as e: logging.error(f"Tile Remove Error ({filename}): {e}", exc_info=True)

    def remove_selected_tile(self):
        """Removes the tile selected in the app's listbox."""
        view = self.view
        try:
            logging.info("Tile Remove Selected")
            if not hasattr(view.app, 'file_listbox'): logging.error("No 'file_listbox' in app."); return
            indices = view.app.file_listbox.curselection()
            if not indices: messagebox.showwarning("Remove", "Select image in list."); return
            filename = view.app.file_listbox.get(indices[0])
            self.remove_tile(filename) # Call own method
        except Exception as e: logging.error(f"Tile Remove Selected Error: {e}", exc_info=True)