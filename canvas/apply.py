# --- canvas/apply.py ---
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw
import logging
import os

def run_apply_canvas_to_images(canvas_window):
    """Applies changes from overlay to tiles and handles palette changes."""
    try:
        view = canvas_window
        if not (hasattr(view, 'current_scale_factor') and abs(view.current_scale_factor - 1.0) < 0.001):
            messagebox.showwarning("Zoom Error", "Please reset zoom to 100% before applying (hotkey Z)")
            logging.warning("Apply cancelled: Zoom not 100%.")
            return

        # Set applying_canvas flag for palette handling
        if hasattr(view, 'app'):
            view.app.applying_canvas = True

        has_overlay = view.pasted_overlay_pil_image is not None
        has_palette_changes = False

        if not has_overlay and not view.images:
            messagebox.showinfo("Apply", "No changes to apply.")
            return

        if has_overlay:
            # Get overlay info
            overlay_width = view.pasted_overlay_pil_image.width
            overlay_height = view.pasted_overlay_pil_image.height
            overlay_pixels = view.pasted_overlay_pil_image.load()
            apply_origin_x = view.pasted_overlay_offset[0]
            apply_origin_y = view.pasted_overlay_offset[1]

            # Get overlay opacity
            overlay_opacity = view.app.overlay_opacity_var.get() / 100.0 if hasattr(view.app, 'overlay_opacity_var') else 1.0

            logging.info(f"Apply: Overlay size: {overlay_width}x{overlay_height}, Origin: ({apply_origin_x},{apply_origin_y})")

        processed_count = 0
        error_count = 0

        # Iterate Tiles
        for filename, image_info in list(view.images.items()):
            if not os.path.exists(filename):
                logging.warning(f"Skip '{filename}': Not found.")
                error_count += 1
                continue

            try:
                tile_item_id = image_info['id']
                if not view.canvas.find_withtag(tile_item_id):
                    logging.warning(f"Skip '{filename}': ID {tile_item_id} not found.")
                    error_count += 1
                    continue

                # Get the initial transparency color for this image
                transparency_color = None
                if 'initial_transparency_color' in image_info:
                    color_hex = image_info['initial_transparency_color'].lstrip('#')
                    transparency_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
                invert_transparency = view.app.invert_transparency.get() if hasattr(view.app, 'invert_transparency') else False
                tolerance = view.app.tolerance_value.get() if hasattr(view.app, 'tolerance_value') else 0

                tile_x = image_info.get('x', 0)
                tile_y = image_info.get('y', 0)

                # Get current image state (includes palette changes)
                current_image = image_info['image']
                if not current_image:
                    continue

                if has_overlay:
                    # Process overlay changes
                    w, h = current_image.size
                    output_tile = Image.new('RGBA', (w, h))
                    output_pixels = output_tile.load()
                    current_pixels = current_image.load()

                    # Pixel processing
                    for px in range(w):
                        for py in range(h):
                            current_rgba = current_pixels[px, py]
                            current_rgb = current_rgba[:3]

                            # Check if pixel matches transparency color
                            is_transparent = False
                            if transparency_color:
                                matches = all(abs(current_rgb[i] - transparency_color[i]) <= tolerance for i in range(3))
                                is_transparent = matches if not invert_transparency else not matches

                            if is_transparent:
                                output_pixels[px, py] = (transparency_color[0], transparency_color[1], transparency_color[2], 255)
                            else:
                                overlay_read_x = tile_x + px - apply_origin_x
                                overlay_read_y = tile_y + py - apply_origin_y
                                if 0 <= overlay_read_x < overlay_width and 0 <= overlay_read_y < overlay_height:
                                    overlay_rgba = overlay_pixels[overlay_read_x, overlay_read_y]
                                    if overlay_rgba[3] > 0:
                                        final_alpha = int(overlay_rgba[3] * overlay_opacity)
                                        if final_alpha > 0:
                                            alpha_factor = final_alpha / 255.0
                                            output_pixels[px, py] = (
                                                int(overlay_rgba[0] * alpha_factor + current_rgba[0] * (1 - alpha_factor)),
                                                int(overlay_rgba[1] * alpha_factor + current_rgba[1] * (1 - alpha_factor)),
                                                int(overlay_rgba[2] * alpha_factor + current_rgba[2] * (1 - alpha_factor)),
                                                255
                                            )
                                        else:
                                            output_pixels[px, py] = current_rgba
                                    else:
                                        output_pixels[px, py] = current_rgba
                                else:
                                    output_pixels[px, py] = current_rgba
                    
                    # Save the processed image
                    output_tile.save(filename)
                else:
                    # Handle palette changes while preserving original transparency
                    if current_image != image_info.get('original_image'):
                        w, h = current_image.size
                        output_tile = Image.new('RGBA', (w, h))
                        output_pixels = output_tile.load()
                        current_pixels = current_image.load()
                        original_pixels = image_info.get('original_image').load()

                        # Process each pixel
                        for px in range(w):
                            for py in range(h):
                                original_rgba = original_pixels[px, py]
                                current_rgba = current_pixels[px, py]
                                original_rgb = original_rgba[:3]

                                # Check if this was originally a transparent pixel
                                is_transparent = False
                                if transparency_color:
                                    matches = all(abs(original_rgb[i] - transparency_color[i]) <= tolerance for i in range(3))
                                    is_transparent = matches if not invert_transparency else not matches

                                if is_transparent:
                                    # Use the original transparency color
                                    output_pixels[px, py] = (transparency_color[0], transparency_color[1], transparency_color[2], 255)
                                else:
                                    # Keep palette-mapped color for non-transparent pixels
                                    output_pixels[px, py] = current_rgba

                        # Save with preserved transparency color
                        output_tile.save(filename)
                        has_palette_changes = True

                # Update grid window
                try:
                    view.grid_window.update_image_in_grid(filename, Image.open(filename))
                except Exception as reload_err:
                    logging.error(f"Grid update failed '{filename}': {reload_err}")

                processed_count += 1

            except Exception as tile_error:
                logging.error(f"Tile proc error '{filename}': {tile_error}", exc_info=True)
                error_count += 1

        # Finish
        if has_overlay or has_palette_changes:
            log_msg = f"Apply complete. Updated: {processed_count}, Errors: {error_count}."
            logging.info(log_msg)
            if error_count > 0:
                messagebox.showerror("Apply Errors", f"{log_msg}\nCheck log.")
            else:
                messagebox.showinfo("Success", log_msg)
        else:
            messagebox.showinfo("Apply", "No changes to apply.")

    except Exception as e:
        logging.error(f"Critical apply error: {e}", exc_info=True)
        messagebox.showerror("Error", f"Apply failed.\n{e}")
    finally:
        # Reset applying_canvas flag
        if hasattr(view, 'app'):
            view.app.applying_canvas = False