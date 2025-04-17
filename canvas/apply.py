# --- canvas/apply.py ---
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw
import logging
import os

def run_apply_canvas_to_images(canvas_view):
    """Applies changes from overlay to tiles, checking zoom first."""
    view = canvas_view
    try:
        logging.info("Apply Logic: Starting...")
        # *** ADD ZOOM CHECK ***
        if not (hasattr(view, 'current_scale_factor') and abs(view.current_scale_factor - 1.0) < 0.001):
             messagebox.showwarning("Zoom Error", "Please reset zoom to 100% before applying.") # Removed hotkey ref
             logging.warning("Apply cancelled: Zoom level is not 100%.")
             return
        # ********************

        # Pre-checks
        if view.pasted_overlay_pil_image is None: messagebox.showerror("Error","Paste overlay first."); logging.error("Apply: No overlay PIL."); return
        if view.pasted_overlay_item_id is None: messagebox.showerror("Error","Overlay ID missing."); logging.error("Apply: Overlay ID is None."); return
        if not view.canvas.gettags(view.pasted_overlay_item_id): messagebox.showerror("Error","Overlay missing."); logging.error(f"Apply: Overlay ID {view.pasted_overlay_item_id} invalid."); view.pasted_overlay_item_id=None; return
        if not view.images: messagebox.showwarning("Warning","No tiles placed."); logging.warning("Apply: No tiles."); return

        # Get Data
        overlay_image_rgba=view.pasted_overlay_pil_image.convert("RGBA"); overlay_pixels=overlay_image_rgba.load()
        overlay_width, overlay_height = overlay_image_rgba.size
        # Use capture origin if available, otherwise overlay offset
        apply_origin_x, apply_origin_y = view.last_capture_origin if view.last_capture_origin is not None else view.pasted_overlay_offset
        apply_origin_x = int(round(apply_origin_x)); apply_origin_y = int(round(apply_origin_y)) # Ensure integer
        bg_color_rgb=view.background_color; has_bg_color = bg_color_rgb is not None
        logging.info(f"Apply: Overlay size: {overlay_width}x{overlay_height}, Effective Origin: ({apply_origin_x},{apply_origin_y})")
        logging.info(f"Apply: BG color: {bg_color_rgb} (Active: {has_bg_color})")
        processed_count=0; error_count=0

        # Iterate Tiles
        for filename, image_info in list(view.images.items()):
            if not os.path.exists(filename): logging.warning(f"Skip '{filename}': Not found."); error_count+=1; continue
            try:
                tile_item_id=image_info['id']
                if not view.canvas.find_withtag(tile_item_id): logging.warning(f"Skip '{filename}': ID {tile_item_id} not found."); error_count+=1; continue
                tile_x=image_info.get('x', 0); tile_y=image_info.get('y', 0) # Integer coords @1.0x
                original_tile=Image.open(filename).convert("RGBA"); original_pixels=original_tile.load()
                w, h=original_tile.size; logging.debug(f"Apply Proc: '{os.path.basename(filename)}': Size ({w}x{h}), Pos ({tile_x},{tile_y})")
                output_tile=Image.new('RGBA', (w, h)); output_pixels=output_tile.load()
                log_bg_match = True
                # Pixel processing
                for px in range(w):
                    for py in range(h):
                        original_rgba=original_pixels[px, py]; original_rgb=original_rgba[:3]
                        is_background = has_bg_color and original_rgb == bg_color_rgb
                        if log_bg_match and has_bg_color and px==0 and py==0 and not is_background: logging.debug(f"Apply: BG NO MATCH {os.path.basename(filename)}@({px},{py}) {original_rgb} vs {bg_color_rgb}")
                        if is_background: output_pixels[px, py]=original_rgba
                        else:
                            overlay_read_x = tile_x + px - apply_origin_x
                            overlay_read_y = tile_y + py - apply_origin_y
                            if 0<=overlay_read_x<overlay_width and 0<=overlay_read_y<overlay_height: output_pixels[px, py]=overlay_pixels[overlay_read_x, overlay_read_y]
                            else: output_pixels[px, py]=original_rgba # Outside overlay
                # Save & Update Grid
                output_tile.save(filename); logging.info(f"Saved '{os.path.basename(filename)}'")
                try: view.grid_window.update_image_in_grid(filename, Image.open(filename))
                except Exception as reload_err: logging.error(f"Grid update failed '{filename}': {reload_err}")
                processed_count+=1
            except Exception as tile_error: logging.error(f"Tile proc error '{filename}': {tile_error}", exc_info=True); error_count+=1
        # Finish
        log_msg=f"'Apply' done. Updated: {processed_count}, Errors: {error_count}."
        logging.info(log_msg)
        if error_count > 0: messagebox.showerror("Apply Errors", f"{log_msg}\nCheck log.")
        else: messagebox.showinfo("Success", log_msg)
    except Exception as e: logging.error(f"Critical apply error: {e}", exc_info=True); messagebox.showerror("Error", f"Apply failed.\n{e}")