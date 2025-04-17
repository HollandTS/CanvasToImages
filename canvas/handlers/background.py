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

    def apply_transparency(self, image, color_tuple, tolerance=None):
        try:
            if not isinstance(color_tuple, tuple) or len(color_tuple) != 3: return image
            if tolerance is None:
                # Try to get from app if available
                if hasattr(self.view, 'app') and hasattr(self.view.app, 'tolerance_value'):
                    tolerance = self.view.app.tolerance_value.get()
                else:
                    tolerance = 0
            img_rgba = image.convert("RGBA"); datas = list(img_rgba.getdata())
            new_data = []
            invert = False
            if hasattr(self.view, 'app') and hasattr(self.view.app, 'invert_transparency'):
                invert = self.view.app.invert_transparency.get()
            def is_close(c1, c2, tol):
                return sum((a-b)**2 for a,b in zip(c1, c2)) <= tol*tol
            for item in datas:
                if is_close(item[:3], color_tuple, tolerance):
                    if invert:
                        new_data.append(item)
                    else:
                        new_data.append((item[0], item[1], item[2], 0))
                else:
                    if invert:
                        new_data.append((item[0], item[1], item[2], 0))
                    else:
                        new_data.append(item)
            img_rgba.putdata(new_data)
            return img_rgba
        except Exception as e: logging.error(f"BG Apply Trans error: {e}", exc_info=True); return image

    def set_color(self, color_hex):
        view = self.view
        try:
            logging.info(f"BG Set Color: Hex: {color_hex}")
            color_hex = color_hex.lstrip('#')
            if len(color_hex) != 6: raise ValueError("Hex color must be 6 digits")
            new_bg_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
            logging.info(f"BG Set Color: RGB tuple: {new_bg_color}")
            view.background_color = new_bg_color

            # Always set the canvas background to white (or your preferred neutral color)
            view.canvas.config(bg='white')

            # --- FULL REDRAW: Remove all draggable items except overlay and re-add ---
            for item_id in view.canvas.find_withtag("draggable"):
                tags = view.canvas.gettags(item_id)
                if "pasted_overlay" not in tags:
                    view.canvas.delete(item_id)
            new_tk_images = []
            logging.info(f"BG Set Color: Redraw debug: images={list(view.images.keys())}")
            for filename, image_info in list(view.images.items()):
                logging.info(f"BG Set Color: Processing {filename}")
                if os.path.exists(filename):
                    logging.info(f"BG Set Color: Reloading {filename} from disk")
                    original_image = Image.open(filename).convert("RGBA")
                else:
                    logging.warning(f"BG Set Color: File not found: {filename}, using in-memory image")
                    original_image = image_info["image"].copy()
                display_image = original_image.copy()
                if view.background_color:
                    logging.info(f"BG Set Color: Applying transparency for {filename} with color {view.background_color}")
                    display_image = self.apply_transparency(display_image, view.background_color)
                else:
                    logging.info(f"BG Set Color: No background color set for {filename}")
                # Re-apply zoom scaling if zoom exists
                if hasattr(view, 'current_scale_factor') and view.current_scale_factor != 1.0:
                    scaled_w = max(1, int(display_image.width * view.current_scale_factor))
                    scaled_h = max(1, int(display_image.height * view.current_scale_factor))
                    display_image = display_image.resize((scaled_w, scaled_h), LANCZOS_RESAMPLE)
                tk_image = ImageTk.PhotoImage(display_image)
                new_tk_images.append(tk_image)
                new_item_id = view.canvas.create_image(image_info["x"], image_info["y"], anchor="nw", image=tk_image, tags=("draggable", filename))
                view.images[filename]['id'] = new_item_id # Update ID
                # Re-apply coordinate scaling if zoom exists
                if hasattr(view, 'current_scale_factor') and view.current_scale_factor != 1.0:
                    view.canvas.scale(new_item_id, image_info["x"], image_info["y"], view.current_scale_factor, view.current_scale_factor)
                if view.pasted_overlay_item_id and view.canvas.find_withtag(view.pasted_overlay_item_id):
                    view.canvas.tag_lower(new_item_id, view.pasted_overlay_item_id)
            view.tk_images = new_tk_images
            logging.info(f"BG Set Color: Redrawn all images from disk.")
        except ValueError as ve: logging.error(f"BG Set Color: Invalid hex '{color_hex}': {ve}"); messagebox.showerror("Error", f"Invalid color: {color_hex}."); view.background_color = None
        except Exception as e: logging.error(f"BG Set Color Error: {e}", exc_info=True); view.background_color = None

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