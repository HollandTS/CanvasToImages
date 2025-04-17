# --- canvas/view.py ---
import tkinter as tk
from tkinter import Canvas, filedialog, messagebox
import logging
import math
import os
import base64
import io
from PIL import Image, ImageTk, ImageDraw

from .handlers.background import BackgroundHandler
from .handlers.interaction import InteractionHandler
from .handlers.overlay import OverlayHandler
from .handlers.tile import TileHandler
from .apply import run_apply_canvas_to_images
from .utils import is_above_canvas

try: LANCZOS_RESAMPLE = Image.Resampling.LANCZOS
except AttributeError: LANCZOS_RESAMPLE = Image.LANCZOS; logging.warning("Using older Pillow Image.LANCZOS filter.")

class CanvasWindow(tk.Frame):
    def __init__(self, parent, grid_window, app, initial_width=1500, initial_height=1500):
        try:
            logging.info("Initializing CanvasWindow View")
            super().__init__(parent)
            self.grid_window = grid_window; self.app = app
            self.canvas_world_width = initial_width
            self.canvas_world_height = initial_height
            self.canvas = Canvas(self, bg="white", bd=0, highlightthickness=0)
            # Set scrollregion based on initial world size
            self.canvas.config(scrollregion=(0, 0, self.canvas_world_width, self.canvas_world_height))
            self.canvas.pack(fill="both", expand=True)
            # Checkbox Frame
            checkbox_frame = tk.Frame(self); checkbox_frame.place(in_=self.canvas, relx=1.0, rely=1.0, x=-5, y=-5, anchor="se")
            self.snap_enabled = tk.BooleanVar(value=True); self.snap_checkbox = tk.Checkbutton(checkbox_frame, text="Snap", variable=self.snap_enabled, bg="#F0F0F0", relief="raised", bd=1, padx=2); self.snap_checkbox.pack(side="right", padx=(2,0))
            self.overlap_enabled = tk.BooleanVar(value=True); self.overlap_checkbox = tk.Checkbutton(checkbox_frame, text="Overlap", variable=self.overlap_enabled, bg="#F0F0F0", relief="raised", bd=1, padx=2); self.overlap_checkbox.pack(side="right", padx=(0,2))
            # State
            self.images = {}; self.tk_images = []; self.background_color = None; self.transparency_color = None; self.pasted_overlay_pil_image = None; self.pasted_overlay_tk_image = None; self.pasted_overlay_item_id = None; self.pasted_overlay_offset = (0, 0); self.current_grid_info = None; self.last_clicked_item_id = None; self.selected_item_ids = set(); self.current_scale_factor = 1.0; self.zoom_label = None; self.zoom_label_after_id = None
            self.last_capture_origin = None
            # Handlers
            self.bg_handler = BackgroundHandler(self); self.tile_handler = TileHandler(self); self.overlay_handler = OverlayHandler(self); self.interaction_handler = InteractionHandler(self)
            # Bindings
            self.canvas.bind("<Button-1>", self.interaction_handler.handle_click); self.canvas.bind("<Control-Button-1>", self.interaction_handler.handle_ctrl_click); self.canvas.bind("<Shift-Button-1>", self.interaction_handler.handle_shift_click); self.canvas.bind("<B1-Motion>", self.interaction_handler.handle_drag); self.canvas.bind("<ButtonRelease-1>", self.interaction_handler.handle_release)
            self.canvas.bind("<ButtonPress-3>", self.interaction_handler.start_box_select); self.canvas.bind("<B3-Motion>", self.interaction_handler.update_box_select); self.canvas.bind("<ButtonRelease-3>", self.interaction_handler.end_box_select)
            self.canvas.bind("<ButtonPress-2>", self.interaction_handler.handle_pan_start); self.canvas.bind("<B2-Motion>", self.interaction_handler.handle_pan_motion); self.canvas.bind("<ButtonRelease-2>", self.interaction_handler.handle_pan_end)
            # *** REMOVED Center View Binding ***
            self.canvas.bind("<Configure>", self.on_canvas_resize); self._redraw_grid_job = None
            self.canvas.bind("<MouseWheel>", self.handle_zoom); self.canvas.bind("<Button-4>", self.handle_zoom); self.canvas.bind("<Button-5>", self.handle_zoom)
            self.canvas.bind("<KeyPress-z>", self.reset_zoom); self.canvas.bind("<KeyPress-Z>", self.reset_zoom) # Keep hotkey on canvas
            self.canvas.focus_set()
            self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set(), add='+')

            logging.info("CanvasWindow View initialized successfully")
            self.after(100, self._draw_canvas_borders); self.after(110, self.draw_grid)
        except Exception as e: logging.error(f"Error initializing CanvasWindow View: {e}", exc_info=True)

    # --- Public Methods ---
    def add_image(self, image, filename, x=0, y=0):
        # Store original image for palette reset
        self.tile_handler.add_tile(image, filename, x, y)
        if filename in self.images:
            self.images[filename]['original_image'] = image.copy()

    def set_transparency_color(self, color_hex):
        self.bg_handler.set_color(color_hex)
        self.transparency_color = color_hex

    def set_background_color(self, color_hex):
        self.set_transparency_color(color_hex)

    def paste_image_from_clipboard(self): self.overlay_handler.paste_from_clipboard()
    def apply_canvas_to_images(self): run_apply_canvas_to_images(self) # Calls zoom check internally
    def is_above_canvas(self, event): return is_above_canvas(self.canvas, event)

    # *** NEW: Method to set world size ***
    def set_world_size(self, width, height):
        """Updates the logical size of the canvas world and redraws."""
        logging.info(f"Setting canvas world size to {width}x{height}")
        self.canvas_world_width = max(1, width) # Ensure minimum size
        self.canvas_world_height = max(1, height)
        # Update scrollregion - coords are always relative to 0,0 at 1.0x zoom
        # Note: Tkinter canvas coords are floats, but scrollregion expects integers or floats.
        # Let's provide floats based on the world size scaled by current zoom.
        # Although, logically, scrollregion should represent the total area at 1.0x?
        # Let's stick to 1.0x for scrollregion definition. Panning/Zooming is relative.
        self.canvas.config(scrollregion=(0, 0, self.canvas_world_width, self.canvas_world_height))
        logging.info(f"Canvas scrollregion set to (0, 0, {self.canvas_world_width}, {self.canvas_world_height})")
        self._draw_canvas_borders() # Redraw borders with new size
        self.draw_grid()           # Redraw grid with new bounds

    # --- Get/Save Canvas Image (MODIFIED - Use Capture Mode) ---
    def get_canvas_as_image(self, capture_mode="View") -> Image.Image | None:
        """Captures canvas content by manual rendering. ASSUMES 1.0x ZOOM."""
        logging.info(f"get_canvas_as_image called (mode={capture_mode}, zoom assumed 1.0x)")
        try:
            self.canvas.update_idletasks()
            if abs(self.current_scale_factor - 1.0) > 0.001: logging.error("get_canvas_as_image requires zoom=1.0x!"); return None

            render_origin_x, render_origin_y = 0, 0; target_width, target_height = 0, 0
            canvas_bbox_l, canvas_bbox_t = 0, 0; canvas_bbox_r, canvas_bbox_b = 0, 0
            items_data_for_render = []; valid_bbox = False

            # 1. Determine Target Area and Collect Items based on capture_mode
            if capture_mode == "Full Canvas":
                logging.debug("Calculating bounds for Full Canvas capture...")
                target_width = self.canvas_world_width; target_height = self.canvas_world_height
                render_origin_x, render_origin_y = 0, 0 # Render origin is canvas 0,0
                canvas_bbox_l, canvas_bbox_t, canvas_bbox_r, canvas_bbox_b = 0, 0, target_width, target_height
                self.last_capture_origin = (0, 0) # Origin is canvas 0,0
                logging.info(f"Full Canvas render Size: {target_width}x{target_height}")
                # Collect ALL draggable items within world bounds
                all_draggable_ids = self.canvas.find_enclosed(0, 0, target_width, target_height)
                for item_id in all_draggable_ids:
                    if "draggable" not in self.canvas.gettags(item_id): continue
                    coords=None; pil_img=None; is_tile=False
                    if item_id == self.pasted_overlay_item_id: coords=self.pasted_overlay_offset; pil_img=self.pasted_overlay_pil_image
                    else:
                        for fname, data in self.images.items():
                            if data['id'] == item_id: coords=(data['x'], data['y']); pil_img=data['image']; is_tile=True; break
                    if coords and pil_img: items_data_for_render.append((item_id, pil_img, coords, is_tile))
                valid_bbox = True # Assume valid if capturing full canvas

            elif capture_mode == "Images Only":
                logging.debug("Calculating bounds for Images Only capture...")
                draggable_items = self.canvas.find_withtag("draggable");
                if not draggable_items: return None
                min_x, min_y=float('inf'),float('inf'); max_x, max_y=float('-inf'),float('-inf');
                for item_id in draggable_items:
                    coords=None; pil_img=None; is_tile=False
                    if item_id == self.pasted_overlay_item_id: coords=self.pasted_overlay_offset; pil_img=self.pasted_overlay_pil_image
                    else:
                        for fname, data in self.images.items():
                            if data['id'] == item_id: coords=(data['x'], data['y']); pil_img=data['image']; is_tile=True; break
                    if coords and pil_img:
                        items_data_for_render.append((item_id, pil_img, coords, is_tile)) # Collect data
                        x,y=coords; w,h=pil_img.size; min_x=min(min_x,x); min_y=min(min_y,y); max_x=max(max_x,x+w); max_y=max(max_y,y+h); valid_bbox=True
                if not valid_bbox: return None
                padding=0; l,t,r,b = min_x-padding,min_y-padding,max_x+padding,max_y+padding
                target_width = int(round(r-l)); target_height = int(round(b-t))
                render_origin_x, render_origin_y = l, t # Origin for rendering is bbox top-left
                self.last_capture_origin = (render_origin_x, render_origin_y) # Store bbox origin
                canvas_bbox_l, canvas_bbox_t, canvas_bbox_r, canvas_bbox_b = l, t, r, b # Use bbox for finding items
                logging.info(f"Images Only render area @1x: ({l},{t})->({r},{b}), Size: {target_width}x{target_height}")

            else: # Default to "View" capture
                logging.debug("Calculating bounds for current view capture (@1.0x)...")
                target_width = self.canvas.winfo_width(); target_height = self.canvas.winfo_height()
                canvas_bbox_l = self.canvas.canvasx(0); canvas_bbox_t = self.canvas.canvasy(0) # At 1.0x these are the TL canvas coords
                canvas_bbox_r = canvas_bbox_l + target_width; canvas_bbox_b = canvas_bbox_t + target_height
                render_origin_x, render_origin_y = canvas_bbox_l, canvas_bbox_t
                self.last_capture_origin = None # Not a specific origin capture
                items_in_view = self.canvas.find_overlapping(canvas_bbox_l, canvas_bbox_t, canvas_bbox_r, canvas_bbox_b)
                for item_id in items_in_view:
                    if "draggable" not in self.canvas.gettags(item_id): continue
                    coords=None; pil_img=None; is_tile=False
                    if item_id == self.pasted_overlay_item_id: coords=self.pasted_overlay_offset; pil_img=self.pasted_overlay_pil_image
                    else:
                        for fname, data in self.images.items():
                            if data['id'] == item_id: coords=(data['x'], data['y']); pil_img=data['image']; is_tile=True; break
                    if coords and pil_img: items_data_for_render.append((item_id, pil_img, coords, is_tile))
                logging.info(f"View capture render size: {target_width}x{target_height}, Area @1x: ({canvas_bbox_l:.0f},{canvas_bbox_t:.0f})->({canvas_bbox_r:.0f},{canvas_bbox_b:.0f})")
                valid_bbox = True # View capture is always valid if dimensions > 0


            if not valid_bbox or target_width <= 0 or target_height <= 0: logging.warning("Render size/bbox invalid."); return None
            target_image = Image.new("RGBA", (target_width, target_height), (255, 255, 255, 0))

            # --- Render Items (always at 1.0x scale) ---
            ordered_render_items = sorted(items_data_for_render, key=lambda item: item[0])
            logging.debug(f"Rendering {len(ordered_render_items)} items for mode '{capture_mode}'...")
            for item_id, pil_to_render, coords_1x, is_tile in ordered_render_items:
                img_to_paste = pil_to_render.copy()
                if is_tile and self.background_color: img_to_paste = self.bg_handler.apply_transparency(img_to_paste, self.background_color)
                paste_x = int(round(coords_1x[0] - render_origin_x))
                paste_y = int(round(coords_1x[1] - render_origin_y))
                img_to_paste_rgba = img_to_paste.convert("RGBA")
                if paste_x < target_width and paste_y < target_height and paste_x + img_to_paste_rgba.width > 0 and paste_y + img_to_paste_rgba.height > 0:
                     target_image.paste(img_to_paste_rgba, (paste_x, paste_y), img_to_paste_rgba)

            logging.info(f"Manual render complete. Output size: {target_image.size}")
            return target_image
        except Exception as e: logging.error(f"Error in get_canvas_as_image: {e}", exc_info=True); return None

    def save_canvas_image(self, file_path, capture_mode="View"):
        logging.info(f"Saving canvas image to {file_path} (Capture Mode: {capture_mode})")
        if not abs(self.current_scale_factor - 1.0) < 0.001: messagebox.showwarning("Zoom Error", "Please reset zoom to 100% before saving."); logging.warning("Save cancelled: Zoom not 100%."); return
        img = self.get_canvas_as_image(capture_mode=capture_mode) # Pass mode
        if img:
            try: img.save(file_path); logging.info(f"Canvas saved: {file_path}"); messagebox.showinfo("Save OK", f"Saved:\n{os.path.basename(file_path)}")
            except Exception as e: logging.error(f"Save canvas error: {e}", exc_info=True); messagebox.showerror("Error", f"Save failed.\n{e}")
        else: messagebox.showerror("Error", "Could not capture canvas image to save.")

    def delete_selection_or_last_clicked(self):
        # (Remains the same)
        items_to_delete = set(); log_prefix = "Delete Item:"
        if self.selected_item_ids: items_to_delete=self.selected_item_ids.copy(); log_prefix=f"Delete Multi ({len(items_to_delete)}):"
        elif self.last_clicked_item_id: items_to_delete.add(self.last_clicked_item_id); log_prefix=f"Delete Last Clicked:"
        else: logging.info("Delete called but no item selected."); return
        deleted_count = 0
        for item_id in items_to_delete:
            if item_id is None: continue
            tags = self.canvas.gettags(item_id);
            if not tags: continue
            item_deleted = False
            if "pasted_overlay" in tags:
                if item_id == self.pasted_overlay_item_id:
                    if hasattr(self.overlay_handler,'_clear_overlay_state'): self.overlay_handler._clear_overlay_state()
                    item_deleted=True
            elif "draggable" in tags and len(tags)>1:
                filename = tags[1]
                if hasattr(self.tile_handler,'remove_tile'): self.tile_handler.remove_tile(filename)
                item_deleted=True
            if item_deleted: deleted_count += 1; logging.debug(f"{log_prefix} Deleted item {item_id}")
        logging.info(f"{log_prefix} Deleted {deleted_count} item(s).")
        self.last_clicked_item_id=None; self.selected_item_ids.clear();
        if hasattr(self.interaction_handler,'clear_selection_visuals'): self.interaction_handler.clear_selection_visuals()

    # --- Zoom Methods ---
    def handle_zoom(self, event):
        # (Remains the same)
        scale_direction = 0.0; zoom_in_factor = 1.15; zoom_out_factor = 1 / zoom_in_factor; min_scale = 0.1 ; max_scale = 8.0
        if event.num == 5 or event.delta < 0: scale_direction = zoom_out_factor
        elif event.num == 4 or event.delta > 0: scale_direction = zoom_in_factor
        else: return
        prospective_new_scale = self.current_scale_factor * scale_direction
        if prospective_new_scale < min_scale or prospective_new_scale > max_scale: return
        new_total_scale_factor = prospective_new_scale
        logging.debug(f"Zooming to scale: {new_total_scale_factor:.2f}")
        canvas_x = self.canvas.canvasx(event.x); canvas_y = self.canvas.canvasy(event.y)
        new_tile_tk_images = [] ; new_overlay_tk_image = None
        try:
            for filename, image_info in self.images.items():
                item_id=image_info['id']; original_pil=image_info['image'];
                if not original_pil: continue
                new_w=max(1,int(original_pil.width*new_total_scale_factor)); new_h=max(1,int(original_pil.height*new_total_scale_factor))
                # Use NEAREST for pixel-perfect zoom
                resized_pil = original_pil.resize((new_w, new_h), Image.NEAREST)
                if self.background_color: resized_pil = self.bg_handler.apply_transparency(resized_pil, self.background_color)
                new_tk = ImageTk.PhotoImage(resized_pil); new_tile_tk_images.append(new_tk)
                if self.canvas.find_withtag(item_id): self.canvas.itemconfig(item_id, image=new_tk)
            if self.pasted_overlay_item_id and self.pasted_overlay_pil_image:
                item_id=self.pasted_overlay_item_id; original_pil=self.pasted_overlay_pil_image
                new_w=max(1,int(original_pil.width*new_total_scale_factor)); new_h=max(1,int(original_pil.height*new_total_scale_factor))
                resized_pil = original_pil.resize((new_w, new_h), Image.NEAREST)
                new_tk = ImageTk.PhotoImage(resized_pil); new_overlay_tk_image = new_tk
                if self.canvas.find_withtag(item_id): self.canvas.itemconfig(item_id, image=new_tk)
            self.tk_images = new_tile_tk_images; self.pasted_overlay_tk_image = new_overlay_tk_image
        except Exception as resize_err: logging.error(f"Zoom resize error: {resize_err}", exc_info=True)
        self.canvas.scale("all", canvas_x, canvas_y, scale_direction, scale_direction)
        self.current_scale_factor = new_total_scale_factor
        if hasattr(self.interaction_handler, '_update_selection_visual_positions'): self.interaction_handler._update_selection_visual_positions()
        self.draw_grid()
        self._show_zoom_percentage(event)

    def reset_zoom(self, event=None):
        # (Remains the same)
        logging.debug("Resetting zoom to 1.0")
        if abs(self.current_scale_factor - 1.0) < 0.001: return
        inverse_scale = 1.0 / self.current_scale_factor
        new_tile_tk_images = [] ; new_overlay_tk_image = None
        try:
            for filename, image_info in self.images.items():
                item_id=image_info['id']; original_pil=image_info['image'];
                if not original_pil: continue
                display_pil=original_pil.copy()
                if self.background_color: display_pil = self.bg_handler.apply_transparency(display_pil, self.background_color)
                new_tk = ImageTk.PhotoImage(display_pil); new_tile_tk_images.append(new_tk)
                if self.canvas.find_withtag(item_id): self.canvas.itemconfig(item_id, image=new_tk)
            if self.pasted_overlay_item_id and self.pasted_overlay_pil_image:
                item_id=self.pasted_overlay_item_id; original_pil=self.pasted_overlay_pil_image
                new_tk = ImageTk.PhotoImage(original_pil); new_overlay_tk_image = new_tk
                if self.canvas.find_withtag(item_id): self.canvas.itemconfig(item_id, image=new_tk)
            self.tk_images = new_tile_tk_images; self.pasted_overlay_tk_image = new_overlay_tk_image
        except Exception as resize_err: logging.error(f"Zoom reset resize error: {resize_err}", exc_info=True)
        self.canvas.scale("all", 0, 0, inverse_scale, inverse_scale)
        self.current_scale_factor = 1.0
        if hasattr(self.interaction_handler, '_update_selection_visual_positions'): self.interaction_handler._update_selection_visual_positions()
        self.draw_grid()
        for item_id in self.canvas.find_withtag("draggable"):
             coords = self.canvas.coords(item_id)
             if coords and hasattr(self.interaction_handler, '_update_item_stored_coords'):
                  self.interaction_handler._update_item_stored_coords(item_id, round(coords[0]), round(coords[1]))
        logging.info("Zoom reset finished.")
        if event: self._show_zoom_percentage(event, force_text="100%")

    # *** MODIFIED ZOOM LABEL POSITIONING ***
    def _show_zoom_percentage(self, event, force_text=None):
        """Displays temporary label AT the cursor (using event window coords)."""
        x_pos = event.x; y_pos = event.y # Position relative to canvas widget
        zoom_text = force_text if force_text else f"{self.current_scale_factor*100:.0f}%"
        bg_color = "lightyellow"
        if self.zoom_label and self.zoom_label.winfo_exists():
            self.zoom_label.config(text=zoom_text); self.zoom_label.place(x=x_pos, y=y_pos, anchor="nw"); self.zoom_label.lift()
        else:
            self.zoom_label = tk.Label(self.canvas, text=zoom_text, bg=bg_color, relief="solid", bd=1, font=("Arial", 9)); self.zoom_label.place(x=x_pos, y=y_pos, anchor="nw"); self.zoom_label.lift()
        if self.zoom_label_after_id: self.after_cancel(self.zoom_label_after_id)
        self.zoom_label_after_id = self.after(1200, self._hide_zoom_label)
    def _hide_zoom_label(self):
        if self.zoom_label and self.zoom_label.winfo_exists(): self.zoom_label.destroy()
        self.zoom_label = None; self.zoom_label_after_id = None

    # --- Grid Methods (Draw using canvas coords, lower border below grid) ---
    def update_grid(self, grid_info): self.current_grid_info = grid_info; self.draw_grid()
    def _draw_canvas_borders(self):
         self.canvas.delete("canvas_border")
         width = self.canvas_world_width; height = self.canvas_world_height
         border_color = "#A0A0A0"; border_width = 1
         # Scale the border coords by the current zoom factor
         scaled_width = width * self.current_scale_factor; scaled_height = height * self.current_scale_factor
         self.canvas.create_rectangle(0, 0, scaled_width, scaled_height, outline=border_color, width=border_width, tags=("canvas_border"))
         self.canvas.tag_lower("canvas_border", "all") # Lower below everything initially
         logging.debug(f"Canvas border drawn at 0,0 to {scaled_width},{scaled_height}")

    def draw_grid(self):
        self.canvas.delete("grid_line"); grid_info=self.current_grid_info;
        if not grid_info: return
        grid_type=grid_info.get("type"); grid_color="#E0E0E0"; grid_tag="grid_line"
        view_x1=self.canvas.canvasx(0); view_y1=self.canvas.canvasy(0); view_x2=self.canvas.canvasx(self.canvas.winfo_width()); view_y2=self.canvas.canvasy(self.canvas.winfo_height())
        world_x1_cv = 0; world_y1_cv = 0; world_x2_cv = self.canvas_world_width*self.current_scale_factor; world_y2_cv = self.canvas_world_height*self.current_scale_factor
        draw_xmin = max(view_x1, world_x1_cv); draw_ymin = max(view_y1, world_y1_cv); draw_xmax = min(view_x2, world_x2_cv); draw_ymax = min(view_y2, world_y2_cv)
        # logging.debug(f"Drawing grid '{grid_type}' in canvas coords ({draw_xmin:.1f},{draw_ymin:.1f}) to ({draw_xmax:.1f},{draw_ymax:.1f})")
        if grid_type=="pixel":
            step=grid_info.get("step");
            if not step or step<=0: return
            scaled_step = step * self.current_scale_factor;
            if scaled_step < 2: return # Avoid drawing too many lines
            start_x = math.floor(draw_xmin / scaled_step) * scaled_step; end_x = math.ceil(draw_xmax / scaled_step) * scaled_step
            start_y = math.floor(draw_ymin / scaled_step) * scaled_step; end_y = math.ceil(draw_ymax / scaled_step) * scaled_step
            for x in range(int(round(start_x)), int(round(end_x + scaled_step)), int(round(scaled_step))): self.canvas.create_line(x, draw_ymin, x, draw_ymax, fill=grid_color, tags=grid_tag)
            for y in range(int(round(start_y)), int(round(end_y + scaled_step)), int(round(scaled_step))): self.canvas.create_line(draw_xmin, y, draw_xmax, y, fill=grid_color, tags=grid_tag)
        elif grid_type=="diamond":
            cell_w=grid_info.get("cell_width"); cell_h=grid_info.get("cell_height");
            if not cell_w or cell_w<=0 or not cell_h or cell_h<=0 or cell_w==0: return
            scaled_cell_w = cell_w * self.current_scale_factor; scaled_cell_h = cell_h * self.current_scale_factor
            if scaled_cell_w < 2 or scaled_cell_h < 1: return
            half_w=scaled_cell_w/2.0; slope1=scaled_cell_h/scaled_cell_w; slope2=-scaled_cell_h/scaled_cell_w
            c1_vals = [draw_ymin-slope1*draw_xmin, draw_ymin-slope1*draw_xmax, draw_ymax-slope1*draw_xmin, draw_ymax-slope1*draw_xmax]; min_c1=min(c1_vals)-scaled_cell_h; max_c1=max(c1_vals)+scaled_cell_h
            c2_vals = [draw_ymin-slope2*draw_xmin, draw_ymin-slope2*draw_xmax, draw_ymax-slope2*draw_xmin, draw_ymax-slope2*draw_xmax]; min_c2=min(c2_vals)-scaled_cell_h; max_c2=max(c2_vals)+scaled_cell_h
            start_k1=math.floor(min_c1/scaled_cell_h); end_k1=math.ceil(max_c1/scaled_cell_h)
            start_k2=math.floor(min_c2/scaled_cell_h); end_k2=math.ceil(max_c2/scaled_cell_h)
            for k in range(start_k1, end_k1 + 1): self.draw_iso_line_segment(slope1, k * scaled_cell_h, draw_xmin, draw_ymin, draw_xmax, draw_ymax, grid_color, grid_tag)
            for k in range(start_k2, end_k2 + 1): self.draw_iso_line_segment(slope2, k * scaled_cell_h, draw_xmin, draw_ymin, draw_xmax, draw_ymax, grid_color, grid_tag)
        # --- Ensure correct stacking order ---
        # Lower grid lines below all draggable items (tiles and overlay)
        if self.canvas.find_withtag(grid_tag): # Only lower if grid lines were drawn
            if self.canvas.find_withtag("draggable"): # Only lower if draggable items exist
                self.canvas.tag_lower(grid_tag, "draggable")

        # Ensure border is below grid (if grid exists), otherwise below all
        if self.canvas.find_withtag("canvas_border"):
            if self.canvas.find_withtag(grid_tag):
                self.canvas.tag_lower("canvas_border", grid_tag)
            else:
                self.canvas.tag_lower("canvas_border", "all")
        # --- End stacking order ---

        logging.debug("Grid drawn and stacking order adjusted.") # Updated log message
    def draw_iso_line_segment(self, slope, intercept_c, xmin, ymin, xmax, ymax, color, tag):
        points=[]; tolerance=0.01; y_at_xmin=slope*xmin+intercept_c; y_at_xmax=slope*xmax+intercept_c
        if ymin<=y_at_xmin<=ymax: points.append((xmin,y_at_xmin))
        if ymin<=y_at_xmax<=ymax: points.append((xmax,y_at_xmax))
        if abs(slope) > 1e-9: x_at_ymin=(ymin-intercept_c)/slope; x_at_ymax=(ymax-intercept_c)/slope;
        if xmin<=x_at_ymin<=xmax: points.append((x_at_ymin,ymin))
        if xmin<=x_at_ymax<=xmax: points.append((x_at_ymax,ymax))
        else:
             if ymin<=intercept_c<=ymax: points.append((xmin,intercept_c)); points.append((xmax,intercept_c))
        valid_points = [];
        for p1 in points:
            is_dupe=False;
            for p2 in valid_points:
                if abs(p1[0]-p2[0])<tolerance and abs(p1[1]-p2[1])<tolerance: is_dupe=True; break
            if not is_dupe: valid_points.append(p1)
        if len(valid_points)>=2:
            p1=valid_points[0]; p2=valid_points[1];
            if abs(p1[0]-p2[0])>tolerance or abs(p1[1]-p2[1])>tolerance: self.canvas.create_line(p1[0],p1[1],p2[0],p2[1],fill=color,tags=tag)
    def on_canvas_resize(self, event):
        self._draw_canvas_borders() # Redraw borders
        if hasattr(self, '_redraw_grid_job') and self._redraw_grid_job: self.after_cancel(self._redraw_grid_job)
        self._redraw_grid_job = self.after(50, self.draw_grid) # Debounce grid

    # --- Layout Save/Load Methods ---
    def get_layout_data(self):
        layout = {"canvas_items": [], "overlay": None, "settings": {}};
        layout["settings"]["capture_origin"] = self.last_capture_origin
        layout["settings"]["canvas_width"] = self.canvas_world_width
        layout["settings"]["canvas_height"] = self.canvas_world_height
        layout["settings"]["capture_mode"] = self.app.capture_mode_var.get() # Save radio button state
        for filename, data in self.images.items(): layout["canvas_items"].append({"filepath": filename, "x": data.get('x', 0), "y": data.get('y', 0)})
        if self.pasted_overlay_item_id and self.canvas.find_withtag(self.pasted_overlay_item_id):
            layout["overlay"] = {"x": self.pasted_overlay_offset[0], "y": self.pasted_overlay_offset[1]}
            # --- Save overlay image data as base64 PNG ---
            if self.pasted_overlay_pil_image:
                buf = io.BytesIO()
                self.pasted_overlay_pil_image.save(buf, format="PNG")
                overlay_bytes = buf.getvalue()
                layout["overlay_image_data"] = base64.b64encode(overlay_bytes).decode("ascii")
        bg_hex = None;
        if self.background_color:
             try: bg_hex = "#{:02x}{:02x}{:02x}".format(*self.background_color)
             except Exception: pass
        layout["settings"]["background_color"] = bg_hex; layout["settings"]["selected_grid"] = self.current_grid_info["name"] if self.current_grid_info else "None"; layout["settings"]["snap_enabled"] = self.snap_enabled.get(); layout["settings"]["overlap_enabled"] = self.overlap_enabled.get(); layout["settings"]["zoom_factor"] = self.current_scale_factor
        return layout
    def apply_layout(self, items_to_place, settings_data, overlay_data, capture_origin=None):
        logging.info("Applying loaded layout...");
        try:
            # Set world size FIRST
            loaded_w = settings_data.get("canvas_width", 1500); loaded_h = settings_data.get("canvas_height", 1500)
            self.set_world_size(loaded_w, loaded_h)
            self.app.canvas_width_var.set(str(loaded_w)); self.app.canvas_height_var.set(str(loaded_h))
            # Reset zoom second
            self.reset_zoom()
            # Clear canvas items and state
            draggable_items = self.canvas.find_withtag("draggable");
            for item_id in draggable_items:
                if self.canvas.find_withtag(item_id): self.canvas.delete(item_id)
            self.images.clear(); self.tk_images.clear(); self.pasted_overlay_pil_image=None; self.pasted_overlay_tk_image=None; self.pasted_overlay_item_id=None; self.pasted_overlay_offset=(0,0); self.last_clicked_item_id=None; self.selected_item_ids.clear();
            if hasattr(self.interaction_handler, 'clear_selection_visuals'): self.interaction_handler.clear_selection_visuals()
            # Apply Settings
            bg_hex = settings_data.get("background_color"); grid_name = settings_data.get("selected_grid", "None"); snap = settings_data.get("snap_enabled", True); overlap = settings_data.get("overlap_enabled", True)
            capture_mode = settings_data.get("capture_mode", "View") # Load capture mode
            if bg_hex: self.set_background_color(bg_hex)
            else: self.background_color = None
            self.snap_enabled.set(snap); self.overlap_enabled.set(overlap);
            self.app.capture_mode_var.set(capture_mode) # Set radio button state
            self.last_capture_origin = tuple(capture_origin) if capture_origin and len(capture_origin) == 2 else None # Store origin
            self.app.selected_grid.set(grid_name); self.app.on_grid_selected() # Apply grid
            # Place Tiles
            for item_info in items_to_place:
                pil_img=item_info.get('pil_image'); fp=item_info.get('filepath'); x=item_info.get('x'); y=item_info.get('y')
                if pil_img and fp and isinstance(x,(int,float)) and isinstance(y,(int,float)): self.add_image(pil_img, fp, int(round(x)), int(round(y)))
            # Store Overlay Offset
            if overlay_data and isinstance(overlay_data.get('x'),(int,float)) and isinstance(overlay_data.get('y'),(int,float)):
                self.pasted_overlay_offset = (int(round(overlay_data['x'])), int(round(overlay_data['y'])))
                logging.info(f"Stored overlay offset: {self.pasted_overlay_offset}")
                # --- Restore overlay image from base64 if present ---
                overlay_img_b64 = settings_data.get("overlay_image_data")
                if overlay_img_b64:
                    try:
                        overlay_bytes = base64.b64decode(overlay_img_b64)
                        overlay_img = Image.open(io.BytesIO(overlay_bytes)).convert("RGBA")
                        self.pasted_overlay_pil_image = overlay_img
                        self.pasted_overlay_tk_image = ImageTk.PhotoImage(overlay_img)
                        if self.pasted_overlay_item_id and self.canvas.find_withtag(self.pasted_overlay_item_id):
                            self.canvas.delete(self.pasted_overlay_item_id)
                        self.pasted_overlay_item_id = self.canvas.create_image(self.pasted_overlay_offset[0], self.pasted_overlay_offset[1], anchor="nw", image=self.pasted_overlay_tk_image, tags=("draggable", "pasted_overlay"))
                        self.update_overlay_stacking()
                        logging.info("Overlay image restored from layout.")
                    except Exception as e:
                        logging.error(f"Failed to restore overlay image from layout: {e}", exc_info=True)
            else: self.pasted_overlay_offset = (0, 0)
            logging.info("Layout apply finished.")
        except Exception as e: logging.error(f"Error applying layout: {e}", exc_info=True); messagebox.showerror("Load Error", f"Failed to apply layout.\n{e}")

    # *** REMOVED center_view_on_content ***

    # --- Other Methods ---
    def select_image(self, index): logging.warning("CanvasWindow.select_image(index) not implemented.")

    def redraw_canvas(self):
        # Get the current color from the app's color_entry
        color = self.app.color_entry.get() if hasattr(self.app, 'color_entry') else '#000000'
        self.set_background_color(color)

    def update_overlay_stacking(self):
        """Raise or lower the overlay image based on the checkbox state."""
        if self.pasted_overlay_item_id and self.canvas.find_withtag(self.pasted_overlay_item_id):
            if hasattr(self.app, 'layer_behind_mode') and self.app.layer_behind_mode.get():
                # Move overlay behind all draggable items
                self.canvas.tag_lower(self.pasted_overlay_item_id, "draggable")
            else:
                # Move overlay above all
                self.canvas.tag_raise(self.pasted_overlay_item_id)

    def remap_all_images_to_palette(self, palette_colors):
        """Remap all images on the canvas to use only the given palette colors."""
        import numpy as np
        from PIL import Image
        # Get transparency color as RGB tuple
        transparency_color = None
        if hasattr(self, 'transparency_color') and self.transparency_color:
            hexval = self.transparency_color.lstrip('#')
            transparency_color = tuple(int(hexval[i:i+2], 16) for i in (0, 2, 4))
        def closest_color(pixel, palette):
            # Find closest color in palette (Euclidean distance in RGB)
            arr = np.array(palette)
            dists = np.sum((arr - pixel) ** 2, axis=1)
            return tuple(arr[np.argmin(dists)])
        for filename, data in self.images.items():
            pil_img = data['image']
            arr = np.array(pil_img.convert('RGB'))
            shape = arr.shape
            arr_flat = arr.reshape(-1, 3)
            remapped = []
            for px in arr_flat:
                if transparency_color and tuple(px) == transparency_color:
                    remapped.append([0,0,0,0])
                else:
                    rgb = closest_color(px, palette_colors)
                    remapped.append([*rgb,255])
            arr_remap = np.array(remapped, dtype=np.uint8).reshape((shape[0], shape[1], 4))
            new_img = Image.fromarray(arr_remap, 'RGBA')
            data['image'] = new_img
            tk_img = ImageTk.PhotoImage(new_img)
            self.tk_images.append(tk_img)
            if self.canvas.find_withtag(data['id']):
                self.canvas.itemconfig(data['id'], image=tk_img)
        logging.info(f"Remapped all images to palette of {len(palette_colors)} colors, preserving transparency.")

    def refresh_all_tiles_to_original(self):
        """Restore all images to their original (pre-palette) state."""
        for filename, data in self.images.items():
            if 'original_image' in data:
                data['image'] = data['original_image']
                tk_img = ImageTk.PhotoImage(data['original_image'])
                self.tk_images.append(tk_img)
                if self.canvas.find_withtag(data['id']):
                    self.canvas.itemconfig(data['id'], image=tk_img)
        logging.info("All tiles restored to original images after palette removal.")

    def set_canvas_background_color(self, color):
        """Set the real background color of the canvas widget."""
        self.canvas.config(bg=color)
        self.background_color_hex = color

    def enable_background_color_pick_mode(self):
        """Enable mode to pick a background color from the canvas with the cursor."""
        self._bg_pick_bind_id = self.canvas.bind('<Button-1>', self._on_pick_background_color)
        self.canvas.config(cursor='cross')

    def _on_pick_background_color(self, event):
        # Get pixel color under cursor
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        # Render the canvas to an image to get the color
        img = self.get_canvas_as_image(capture_mode="View")
        if img and 0 <= x < img.width and 0 <= y < img.height:
            rgb = img.getpixel((x, y))
            if isinstance(rgb, (tuple, list)):
                hex_color = '#{:02x}{:02x}{:02x}'.format(*rgb[:3])
                self.set_canvas_background_color(hex_color)
        # Clean up pick mode
        if hasattr(self, '_bg_pick_bind_id'):
            self.canvas.unbind('<Button-1>', self._bg_pick_bind_id)
            del self._bg_pick_bind_id
        self.canvas.config(cursor='')