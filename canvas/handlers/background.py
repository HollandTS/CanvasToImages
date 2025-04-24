# --- canvas/handlers/background.py ---
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import logging
import os

try: LANCZOS_RESAMPLE = Image.Resampling.LANCZOS
except AttributeError: LANCZOS_RESAMPLE = Image.LANCZOS;

class BackgroundHandler:
    def __init__(self, canvas_view):
        self.view = canvas_view

    def apply_transparency(self, image, color, invert=False):
        """Apply transparency to image based on transparency color.
        When invert is True, only pixels matching the transparency color remain visible."""
        try:
            if not color:
                return image

            # Convert hex color to RGB if it's a string
            if isinstance(color, str):
                color = color.lstrip('#')
                color = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))

            # Convert image to RGBA if it isn't already
            if image.mode != 'RGBA':
                image = image.convert('RGBA')

            # Get image data
            data = image.getdata()
            new_data = []

            # Get tolerance value from canvas window
            tolerance = 0
            if hasattr(self.view, 'app') and hasattr(self.view.app, 'tolerance_value'):
                tolerance = self.view.app.tolerance_value.get()

            # Process each pixel
            for item in data:
                # Get RGB and alpha components
                r, g, b = item[:3]
                alpha = item[3] if len(item) > 3 else 255

                # Check if pixel matches transparency color within tolerance
                matches = all(abs(item[i] - color[i]) <= tolerance for i in range(3))

                if invert:
                    # In invert mode: ONLY matching pixels remain visible
                    if matches:
                        new_data.append((r, g, b, alpha))  # Keep matching pixels visible
                    else:
                        new_data.append((r, g, b, 0))  # Make everything else transparent
                else:
                    # In normal mode: matching pixels become transparent
                    if matches:
                        new_data.append((r, g, b, 0))  # Make matching pixels transparent
                    else:
                        new_data.append((r, g, b, alpha))  # Keep non-matching pixels as they are

            # Create new image with updated data
            new_image = Image.new('RGBA', image.size)
            new_image.putdata(new_data)
            return new_image

        except Exception as e:
            logging.error(f"Error applying transparency: {e}", exc_info=True)
            return image

    def set_color(self, color_hex):
        """Set the transparency color and update all images."""
        view = self.view
        try:
            logging.info(f"Setting transparency color: {color_hex}")
            color_hex = color_hex.lstrip('#')
            if len(color_hex) != 6:
                raise ValueError("Hex color must be 6 digits")
            
            # Store the transparency color
            view.transparency_color = color_hex
            
            # Trigger a redraw of the canvas to update all images
            if hasattr(view, 'redraw_canvas'):
                view.redraw_canvas()
            
        except ValueError as ve:
            logging.error(f"Invalid transparency color hex '{color_hex}': {ve}")
            messagebox.showerror("Error", f"Invalid color: {color_hex}.")
            view.transparency_color = None
        except Exception as e:
            logging.error(f"Error setting transparency color: {e}", exc_info=True)
            view.transparency_color = None

    # *** CORRECTED SIGNATURE: Only accept event directly ***
    def handle_pick_click(self, event):
        """Handles clicking on canvas to pick background color."""
        view = self.view
        try:
            logging.debug("BG Pick: Mode active.")
            # Find item using event coords
            canvas_x = view.canvas.canvasx(event.x); canvas_y = view.canvas.canvasy(event.y)
            item_id = view.interaction_handler._find_draggable_item_canvas(canvas_x, canvas_y)

            if item_id and "pasted_overlay" not in view.canvas.gettags(item_id): # Ensure it's not the overlay
                filename = None
                for fname, data in view.images.items():
                    if data['id'] == item_id: filename = fname; break
                if filename and filename in view.images:
                    clicked_image_info = view.images[filename]
                    img_coords = view.canvas.coords(item_id)
                    if img_coords:
                        # Map canvas click coords back to original image coords
                        bbox = view.canvas.bbox(item_id)
                        if bbox and (bbox[2]-bbox[0])>0 and (bbox[3]-bbox[1])>0:
                             prop_x = (canvas_x - bbox[0]) / (bbox[2] - bbox[0]); prop_y = (canvas_y - bbox[1]) / (bbox[3] - bbox[1])
                             original_image = clicked_image_info["image"]
                             orig_px = int(prop_x * original_image.width); orig_py = int(prop_y * original_image.height)
                             if 0 <= orig_px < original_image.width and 0 <= orig_py < original_image.height:
                                 rgba = original_image.convert("RGBA").getpixel((orig_px, orig_py))
                                 hex_c = "#{:02x}{:02x}{:02x}".format(*rgba[:3])
                                 logging.info(f"BG Pick: Item {item_id}, File {os.path.basename(filename)}, Rel ({orig_px},{orig_py}). Hex: {hex_c}")
                                 view.app.select_background_color(hex_c) # Call app method
                             else: logging.warning("BG Pick: Click mapped outside tile bounds."); view.app.cancel_select_background_color()
                        else: logging.warning("BG Pick: Bad bbox for mapping."); view.app.cancel_select_background_color()
                    else: logging.warning("BG Pick: Couldn't get coords."); view.app.cancel_select_background_color()
                else: logging.warning(f"BG Pick: Clicked item {item_id} has no matching file."); view.app.cancel_select_background_color()
            else: logging.info("BG Pick: Click missed valid tile or hit overlay."); view.app.cancel_select_background_color()
        except Exception as e:
            logging.error(f"Error during background pick click: {e}", exc_info=True)
            view.app.cancel_select_background_color()