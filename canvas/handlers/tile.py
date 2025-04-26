# --- canvas/handlers/tile.py ---
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import logging

class TileHandler:
    def __init__(self, canvas_view):
        self.view = canvas_view

    def add_tile(self, image, filename, x=0, y=0):
        """Add a tile to the canvas, accounting for scroll position."""
        try:
            # Convert screen coordinates to canvas coordinates
            canvas_x = int(round(self.view.canvas.canvasx(x)))
            canvas_y = int(round(self.view.canvas.canvasy(y)))
            
            # Create display version of image
            display_image = image.copy()
            if self.view.transparency_color:
                hex_color = self.view.transparency_color.lstrip('#')
                color_tuple = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                display_image = self.view.bg_handler.apply_transparency(
                    display_image,
                    color_tuple,
                    invert=self.view.app.invert_transparency.get() if hasattr(self.view.app, 'invert_transparency') else False
                )
            
            # Create Tkinter image and add to canvas
            tk_image = ImageTk.PhotoImage(display_image)
            self.view.tk_images.append(tk_image)
            
            # Create canvas item
            item_id = self.view.canvas.create_image(
                canvas_x, canvas_y,
                image=tk_image,
                anchor="nw",
                tags=("draggable", filename)
            )
            
            # Store image data
            self.view.images[filename] = {
                'image': image,
                'id': item_id,
                'x': canvas_x,
                'y': canvas_y,
                'z_index': self.view.next_z_index
            }
            
            # Update z-index
            self.view.next_z_index += 1
            
            # Update layers window if it exists
            if hasattr(self.view.app, 'layers_window') and self.view.app.layers_window:
                self.view.app.layers_window.refresh_layers()
                
            return item_id
            
        except Exception as e:
            logging.error(f"Error adding tile: {e}", exc_info=True)
            return None

    def remove_tile(self, filename):
        """Remove a tile from the canvas."""
        try:
            if filename in self.view.images:
                item_id = self.view.images[filename]['id']
                if self.view.canvas.find_withtag(item_id):
                    self.view.canvas.delete(item_id)
                del self.view.images[filename]
                
                # Update layers window if it exists
                if hasattr(self.view.app, 'layers_window') and self.view.app.layers_window:
                    self.view.app.layers_window.refresh_layers()
                    
        except Exception as e:
            logging.error(f"Error removing tile: {e}", exc_info=True)

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