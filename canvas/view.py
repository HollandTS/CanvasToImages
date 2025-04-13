# --- canvas/view.py ---
import tkinter as tk
from tkinter import Canvas, filedialog, messagebox
import logging
import math
import os
from PIL import Image, ImageTk, ImageDraw # Use ImageDraw for rendering

# Import handlers and other necessary modules
from .handlers.background import BackgroundHandler
from .handlers.interaction import InteractionHandler
from .handlers.overlay import OverlayHandler
from .handlers.tile import TileHandler
from .apply import run_apply_canvas_to_images
from .utils import is_above_canvas

try: LANCZOS_RESAMPLE = Image.Resampling.LANCZOS
except AttributeError: LANCZOS_RESAMPLE = Image.LANCZOS; logging.warning("Using older Pillow Image.LANCZOS filter.")

class CanvasWindow(tk.Frame):
    def __init__(self, parent, grid_window, app):
        try:
            logging.info("Initializing CanvasWindow View")
            super().__init__(parent)
            self.grid_window = grid_window; self.app = app
            self.canvas = Canvas(self, width=400, height=600, bg="white", bd=0, highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)
            # Checkbox Frame
            checkbox_frame = tk.Frame(self.canvas); checkbox_frame.place(relx=1.0, rely=1.0, x=-5, y=-5, anchor="se")
            self.snap_enabled = tk.BooleanVar(value=True); self.snap_checkbox = tk.Checkbutton(checkbox_frame, text="Snap", variable=self.snap_enabled, bg="#F0F0F0", relief="raised", bd=1, padx=2); self.snap_checkbox.pack(side="right", padx=(2,0))
            self.overlap_enabled = tk.BooleanVar(value=True); self.overlap_checkbox = tk.Checkbutton(checkbox_frame, text="Overlap", variable=self.overlap_enabled, bg="#F0F0F0", relief="raised", bd=1, padx=2); self.overlap_checkbox.pack(side="right", padx=(0,2))
            # State
            self.images = {}; self.tk_images = []; self.background_color = None; self.pasted_overlay_pil_image = None; self.pasted_overlay_tk_image = None; self.pasted_overlay_item_id = None; self.pasted_overlay_offset = (0, 0); self.current_grid_info = None; self.last_clicked_item_id = None; self.selected_item_ids = set(); self.current_scale_factor = 1.0; self.zoom_label = None; self.zoom_label_after_id = None
            self.last_capture_origin = None
            # Handlers
            self.bg_handler = BackgroundHandler(self); self.tile_handler = TileHandler(self); self.overlay_handler = OverlayHandler(self); self.interaction_handler = InteractionHandler(self)
            # Bindings
            self.canvas.bind("<Button-1>", self.interaction_handler.handle_click); self.canvas.bind("<Control-Button-1>", self.interaction_handler.handle_ctrl_click); self.canvas.bind("<Shift-Button-1>", self.interaction_handler.handle_shift_click); self.canvas.bind("<B1-Motion>", self.interaction_handler.handle_drag); self.canvas.bind("<ButtonRelease-1>", self.interaction_handler.handle_release)
            self.canvas.bind("<ButtonPress-3>", self.interaction_handler.start_box_select); self.canvas.bind("<B3-Motion>", self.interaction_handler.update_box_select); self.canvas.bind("<ButtonRelease-3>", self.interaction_handler.end_box_select)
            # Panning Bindings
            self.canvas.bind("<ButtonPress-2>", self.interaction_handler.handle_pan_start)
            self.canvas.bind("<B2-Motion>", self.interaction_handler.handle_pan_motion)
            self.canvas.bind("<ButtonRelease-2>", self.interaction_handler.handle_pan_end)
            # Center View Binding
            self.canvas.bind("<Double-Button-2>", self.center_view_on_content) # Direct call
            # Other Bindings
            self.canvas.bind("<Configure>", self.on_canvas_resize); self._redraw_grid_job = None
            self.canvas.bind("<MouseWheel>", self.handle_zoom); self.canvas.bind("<Button-4>", self.handle_zoom); self.canvas.bind("<Button-5>", self.handle_zoom)
            # *** Bind Zoom Reset Hotkey ('z') to the canvas widget ***
            self.canvas.bind("<KeyPress-z>", self.reset_zoom)
            self.canvas.bind("<KeyPress-Z>", self.reset_zoom)
            # *** Make canvas focusable to receive key presses ***
            self.canvas.focus_set()
            # Bind click on canvas background to set focus (useful if user clicks away)
            self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set(), add='+')


            logging.info("CanvasWindow View initialized successfully")
        except Exception as e: logging.error(f"Error initializing CanvasWindow View: {e}", exc_info=True)


    # --- Public Methods ---
    def add_image(self, image, filename, x=0, y=0): self.tile_handler.add_tile(image, filename, x, y)
    def set_background_color(self, color_hex): self.bg_handler.set_color(color_hex)
    def paste_image_from_clipboard(self): self.overlay_handler.paste_from_clipboard()
    def apply_canvas_to_images(self): run_apply_canvas_to_images(self) # Calls zoom check internally
    def is_above_canvas(self, event): return is_above_canvas(self.canvas, event)

    # *** REWORKED get_canvas_as_image (Manual Render, Apply Transparency) ***
    def get_canvas_as_image(self, capture_full=False) -> Image.Image | None:
        """Captures canvas content by manual rendering. ASSUMES 1.0x ZOOM."""
        logging.info(f"get_canvas_as_image called (capture_full={capture_full}, zoom assumed 1.0x)")
        try:
            self.canvas.update_idletasks()
            # Assume zoom check happened in caller (Save/Copy)
            render_origin_x, render_origin_y = 0, 0
            target_width, target_height = 0, 0
            canvas_bbox_l, canvas_bbox_t, canvas_bbox_r, canvas_bbox_b = 0, 0, 0, 0

            if capture_full:
                logging.debug("Calculating bounds for full layout capture (@1.0x)...")
                draggable_items = self.canvas.find_withtag("draggable");
                if not draggable_items: return None
                min_x, min_y=float('inf'),float('inf'); max_x, max_y=float('-inf'),float('-inf'); valid_bbox=False
                items_data_for_render = [] # Store (id, pil, coords_1x, is_tile)
                for item_id in draggable_items:
                    coords=None; pil_img=None; is_tile=False
                    if item_id == self.pasted_overlay_item_id: coords=self.pasted_overlay_offset; pil_img=self.pasted_overlay_pil_image
                    else:
                        for fname, data in self.images.items():
                            if data['id'] == item_id: coords=(data['x'], data['y']); pil_img=data['image']; is_tile=True; break
                    if coords and pil_img:
                        items_data_for_render.append((item_id, pil_img, coords, is_tile))
                        x,y=coords; w,h=pil_img.size; min_x=min(min_x,x); min_y=min(min_y,y); max_x=max(max_x,x+w); max_y=max(max_y,y+h); valid_bbox=True
                if not valid_bbox: return None
                padding=0; l,t,r,b = min_x-padding,min_y-padding,max_x+padding,max_y+padding
                target_width = int(round(r-l)); target_height = int(round(b-t))
                render_origin_x, render_origin_y = l, t # Origin for rendering is bbox top-left (@1.0x)
                self.last_capture_origin = (render_origin_x, render_origin_y) # Store for paste
                canvas_bbox_l, canvas_bbox_t, canvas_bbox_r, canvas_bbox_b = l, t, r, b # Bbox for finding items
                logging.info(f"Full layout render area @1x: ({l},{t})->({r},{b}), Size: {target_width}x{target_height}")
            else: # Capture current view (@ 1.0x zoom)
                logging.debug("Calculating bounds for current view capture (@1.0x)...")
                target_width = self.canvas.winfo_width(); target_height = self.canvas.winfo_height()
                canvas_bbox_l = self.canvas.canvasx(0); canvas_bbox_t = self.canvas.canvasy(0)
                canvas_bbox_r = self.canvas.canvasx(target_width); canvas_bbox_b = self.canvas.canvasy(target_height)
                render_origin_x, render_origin_y = canvas_bbox_l, canvas_bbox_t
                self.last_capture_origin = None # Not a full capture
                # Collect item data within view bbox
                items_in_view = self.canvas.find_overlapping(canvas_bbox_l, canvas_bbox_t, canvas_bbox_r, canvas_bbox_b)
                items_data_for_render = []
                for item_id in items_in_view:
                    if "draggable" not in self.canvas.gettags(item_id): continue
                    coords=None; pil_img=None; is_tile=False
                    if item_id == self.pasted_overlay_item_id: coords=self.pasted_overlay_offset; pil_img=self.pasted_overlay_pil_image
                    else:
                        for fname, data in self.images.items():
                            if data['id'] == item_id: coords=(data['x'], data['y']); pil_img=data['image']; is_tile=True; break
                    if coords and pil_img: items_data_for_render.append((item_id, pil_img, coords, is_tile))
                logging.info(f"View capture render size: {target_width}x{target_height}, Area @1x: ({canvas_bbox_l:.0f},{canvas_bbox_t:.0f})->({canvas_bbox_r:.0f},{canvas_bbox_b:.0f})")

            if target_width <= 0 or target_height <= 0: logging.warning("Render size invalid."); return None
            target_image = Image.new("RGBA", (target_width, target_height), (255, 255, 255, 0))

            # --- Render Items (at 1.0x scale) ---
            ordered_render_items = sorted(items_data_for_render, key=lambda item: item[0]) # Sort by canvas ID
            logging.debug(f"Rendering {len(ordered_render_items)} items...")
            for item_id, pil_to_render, coords_1x, is_tile in ordered_render_items:
                # Prep image: Use original PIL, apply transparency
                img_to_paste = pil_to_render.copy()
                if is_tile and self.background_color: img_to_paste = self.bg_handler.apply_transparency(img_to_paste, self.background_color)
                # Calculate paste position relative to the capture origin (render_origin_x/y)
                paste_x = int(round(coords_1x[0] - render_origin_x))
                paste_y = int(round(coords_1x[1] - render_origin_y))
                img_to_paste_rgba = img_to_paste.convert("RGBA")
                target_image.paste(img_to_paste_rgba, (paste_x, paste_y), img_to_paste_rgba)

            logging.info(f"Manual render complete. Output size: {target_image.size}")
            return target_image
        except Exception as e: logging.error(f"Error in get_canvas_as_image: {e}", exc_info=True); return None

    def save_canvas_image(self, file_path, capture_full=False):
        logging.info(f"Saving canvas image to {file_path} (Capture Full: {capture_full})")
        # Check Zoom Level
        if not abs(self.current_scale_factor - 1.0) < 0.001:
            messagebox.showwarning("Zoom Error", "Please reset zoom to 100% before saving."); logging.warning("Save cancelled: Zoom not 100%."); return
        img = self.get_canvas_as_image(capture_full=capture_full)
        if img:
            try: img.save(file_path); logging.info(f"Canvas saved: {file_path}"); messagebox.showinfo("Save OK", f"Saved:\n{os.path.basename(file_path)}")
            except Exception as e: logging.error(f"Save canvas error: {e}", exc_info=True); messagebox.showerror("Error", f"Save failed.\n{e}")
        else: messagebox.showerror("Error", "Could not capture canvas image to save.")

    def delete_selection_or_last_clicked(self):
        # (Remains the same - no message box)
        items_to_delete = set(); log_prefix = "Delete Item:"
        if self.selected_item_ids: items_to_delete=self.selected_item_ids.copy(); log_prefix=f"Delete Multi ({len(items_to_delete)}):"
        elif self.last_clicked_item_id: items_to_delete.add(self.last_clicked_item_id); log_prefix=f"Delete Last Clicked:"
        else: logging.info("Delete called but no item selected."); return
        deleted_count = 0
        for item_id in items_to_delete:
            if item_id is None: continue
            tags = self.canvas.gettags(item_id);
            if not tags: logging.warning(f"{log_prefix} Item {item_id} gone."); continue
            item_deleted = False
            if "pasted_overlay" in tags:
                if item_id == self.pasted_overlay_item_id:
                    if hasattr(self.overlay_handler,'_clear_overlay_state'): self.overlay_handler._clear_overlay_state()
                    item_deleted=True; logging.debug(f"{log_prefix} Removed overlay {item_id}")
            elif "draggable" in tags and len(tags)>1:
                filename = tags[1]
                if hasattr(self.tile_handler,'remove_tile'): self.tile_handler.remove_tile(filename)
                item_deleted=True; logging.debug(f"{log_prefix} Removed tile '{filename}' ID {item_id}")
            else: logging.warning(f"{log_prefix} Item {item_id} unknown tags: {tags}.")
            if item_deleted: deleted_count += 1
        logging.info(f"{log_prefix} Deleted {deleted_count} item(s).")
        self.last_clicked_item_id=None; self.selected_item_ids.clear();
        if hasattr(self.interaction_handler,'clear_selection_visuals'): self.interaction_handler.clear_selection_visuals()

    # --- Zoom Methods ---
    def handle_zoom(self, event):
        scale_direction = 0.0; zoom_in_factor = 1.15; zoom_out_factor = 1 / zoom_in_factor; min_scale = 0.1 ; max_scale = 8.0
        if event.num == 5 or event.delta < 0: scale_direction = zoom_out_factor
        elif event.num == 4 or event.delta > 0: scale_direction = zoom_in_factor
        else: return
        prospective_new_scale = self.current_scale_factor * scale_direction
        if prospective_new_scale < min_scale or prospective_new_scale > max_scale: return
        new_total_scale_factor = prospective_new_scale
        logging.debug(f"Zooming to scale: {new_total_scale_factor:.2f}")
        canvas_x = self.canvas.canvasx(event.x); canvas_y = self.canvas.canvasy(event.y)
        # Update Images
        new_tile_tk_images = [] ; new_overlay_tk_image = None
        try:
            for filename, image_info in self.images.items():
                item_id=image_info['id']; original_pil=image_info['image'];
                if not original_pil: continue
                new_w=max(1,int(original_pil.width*new_total_scale_factor)); new_h=max(1,int(original_pil.height*new_total_scale_factor))
                resized_pil = original_pil.resize((new_w, new_h), LANCZOS_RESAMPLE)
                if self.background_color: resized_pil = self.bg_handler.apply_transparency(resized_pil, self.background_color)
                new_tk = ImageTk.PhotoImage(resized_pil); new_tile_tk_images.append(new_tk)
                if self.canvas.find_withtag(item_id): self.canvas.itemconfig(item_id, image=new_tk)
            if self.pasted_overlay_item_id and self.pasted_overlay_pil_image:
                item_id=self.pasted_overlay_item_id; original_pil=self.pasted_overlay_pil_image
                new_w=max(1,int(original_pil.width*new_total_scale_factor)); new_h=max(1,int(original_pil.height*new_total_scale_factor))
                resized_pil = original_pil.resize((new_w, new_h), LANCZOS_RESAMPLE)
                new_tk = ImageTk.PhotoImage(resized_pil); new_overlay_tk_image = new_tk
                if self.canvas.find_withtag(item_id): self.canvas.itemconfig(item_id, image=new_tk)
            self.tk_images = new_tile_tk_images; self.pasted_overlay_tk_image = new_overlay_tk_image
        except Exception as resize_err: logging.error(f"Zoom resize error: {resize_err}", exc_info=True)
        # Scale Coords, Update State, Redraw
        self.canvas.scale("all", canvas_x, canvas_y, scale_direction, scale_direction)
        self.current_scale_factor = new_total_scale_factor
        if hasattr(self.interaction_handler, '_update_selection_visual_positions'): self.interaction_handler._update_selection_visual_positions()
        self.draw_grid() # Redraw grid is important after scaling
        self._show_zoom_percentage(event)

    def reset_zoom(self, event=None): # Accept event argument
        logging.debug("Resetting zoom to 1.0")
        if abs(self.current_scale_factor - 1.0) < 0.001: logging.debug("Zoom already 1.0x."); return
        inverse_scale = 1.0 / self.current_scale_factor
        # Update Images
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
        # Scale Coords & Update State
        self.canvas.scale("all", 0, 0, inverse_scale, inverse_scale)
        self.current_scale_factor = 1.0
        if hasattr(self.interaction_handler, '_update_selection_visual_positions'): self.interaction_handler._update_selection_visual_positions()
        self.draw_grid()
        # Update stored coords
        for item_id in self.canvas.find_withtag("draggable"):
             coords = self.canvas.coords(item_id)
             if coords and hasattr(self.interaction_handler, '_update_item_stored_coords'):
                  self.interaction_handler._update_item_stored_coords(item_id, round(coords[0]), round(coords[1]))
        logging.info("Zoom reset finished.")
        if event: self._show_zoom_percentage(event, force_text="100%") # Show label if triggered by key

    # *** MODIFIED ZOOM LABEL POSITIONING ***
    def _show_zoom_percentage(self, event, force_text=None):
        """Displays temporary label AT the cursor (using event window coords)."""
        # Use event.x/y relative to the canvas widget
        x_pos = event.x # Position label's top-left AT the cursor x
        y_pos = event.y # Position label's top-left AT the cursor y
        zoom_text = force_text if force_text else f"{self.current_scale_factor*100:.0f}%"
        bg_color = "lightyellow"

        if self.zoom_label and self.zoom_label.winfo_exists():
            self.zoom_label.config(text=zoom_text)
            self.zoom_label.place(x=x_pos, y=y_pos, anchor="nw") # Place relative to canvas
            self.zoom_label.lift()
        else:
            self.zoom_label = tk.Label(self.canvas, text=zoom_text, bg=bg_color, relief="solid", bd=1, font=("Arial", 9))
            self.zoom_label.place(x=x_pos, y=y_pos, anchor="nw") # Place relative to canvas
            self.zoom_label.lift()
        if self.zoom_label_after_id: self.after_cancel(self.zoom_label_after_id)
        self.zoom_label_after_id = self.after(1200, self._hide_zoom_label)

    def _hide_zoom_label(self):
        if self.zoom_label and self.zoom_label.winfo_exists(): self.zoom_label.destroy()
        self.zoom_label = None; self.zoom_label_after_id = None

    # --- Grid Methods (Draw using canvas coords) ---
    def update_grid(self, grid_info): self.current_grid_info = grid_info; self.draw_grid()
    def draw_grid(self):
        self.canvas.delete("grid_line"); grid_info=self.current_grid_info;
        if not grid_info: return
        grid_type=grid_info.get("type"); grid_color="#E0E0E0"; grid_tag="grid_line"
        view_x1=self.canvas.canvasx(0); view_y1=self.canvas.canvasy(0); view_x2=self.canvas.canvasx(self.canvas.winfo_width()); view_y2=self.canvas.canvasy(self.canvas.winfo_height())
        # logging.debug(f"Drawing grid '{grid_type}' in canvas coords ({view_x1:.1f},{view_y1:.1f}) to ({view_x2:.1f},{view_y2:.1f})")
        if grid_type=="pixel":
            step=grid_info.get("step");
            if not step or step<=0: return
            start_x = math.floor(view_x1/step)*step; end_x = math.ceil(view_x2/step)*step; start_y = math.floor(view_y1/step)*step; end_y = math.ceil(view_y2/step)*step
            for x in range(start_x, end_x+step, step): self.canvas.create_line(x,view_y1,x,view_y2,fill=grid_color,tags=grid_tag)
            for y in range(start_y, end_y+step, step): self.canvas.create_line(view_x1,y,view_x2,y,fill=grid_color,tags=grid_tag)
        elif grid_type=="diamond":
            cell_w=grid_info.get("cell_width"); cell_h=grid_info.get("cell_height");
            if not cell_w or cell_w<=0 or not cell_h or cell_h<=0 or cell_w==0: return
            half_w=cell_w/2.0; slope1=cell_h/cell_w; slope2=-cell_h/cell_w
            c1_vals = [view_y1-slope1*view_x1, view_y1-slope1*view_x2, view_y2-slope1*view_x1, view_y2-slope1*view_x2]; min_c1=min(c1_vals)-cell_h; max_c1=max(c1_vals)+cell_h
            c2_vals = [view_y1-slope2*view_x1, view_y1-slope2*view_x2, view_y2-slope2*view_x1, view_y2-slope2*view_x2]; min_c2=min(c2_vals)-cell_h; max_c2=max(c2_vals)+cell_h
            start_k1=math.floor(min_c1/cell_h); end_k1=math.ceil(max_c1/cell_h)
            start_k2=math.floor(min_c2/cell_h); end_k2=math.ceil(max_c2/cell_h)
            for k in range(start_k1, end_k1 + 1): self.draw_iso_line_segment(slope1, k * cell_h, view_x1, view_y1, view_x2, view_y2, grid_color, grid_tag)
            for k in range(start_k2, end_k2 + 1): self.draw_iso_line_segment(slope2, k * cell_h, view_x1, view_y1, view_x2, view_y2, grid_color, grid_tag)
        self.canvas.tag_lower(grid_tag,"all"); # logging.debug("Grid drawn.")
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
        # *** Check length before drawing ***
        if len(valid_points)>=2:
            p1=valid_points[0]; p2=valid_points[1];
            if abs(p1[0]-p2[0])>tolerance or abs(p1[1]-p2[1])>tolerance: self.canvas.create_line(p1[0],p1[1],p2[0],p2[1],fill=color,tags=tag)
        # else: logging.debug("Not enough valid points for line segment.")
    def on_canvas_resize(self, event):
        if hasattr(self, '_redraw_grid_job') and self._redraw_grid_job: self.after_cancel(self._redraw_grid_job)
        self._redraw_grid_job = self.after(150, self.draw_grid)

    # --- Layout Save/Load Methods ---
    def get_layout_data(self):
        layout = {"canvas_items": [], "overlay": None, "settings": {}};
        layout["settings"]["capture_origin"] = self.last_capture_origin
        for filename, data in self.images.items(): layout["canvas_items"].append({"filepath": filename, "x": data.get('x', 0), "y": data.get('y', 0)})
        if self.pasted_overlay_item_id and self.canvas.find_withtag(self.pasted_overlay_item_id): layout["overlay"] = {"x": self.pasted_overlay_offset[0], "y": self.pasted_overlay_offset[1]}
        bg_hex = None;
        if self.background_color:
             try: bg_hex = "#{:02x}{:02x}{:02x}".format(*self.background_color)
             except Exception: pass
        layout["settings"]["background_color"] = bg_hex; layout["settings"]["selected_grid"] = self.current_grid_info["name"] if self.current_grid_info else "None"; layout["settings"]["snap_enabled"] = self.snap_enabled.get(); layout["settings"]["overlap_enabled"] = self.overlap_enabled.get(); layout["settings"]["zoom_factor"] = self.current_scale_factor
        return layout
    def apply_layout(self, items_to_place, settings_data, overlay_data, capture_origin=None):
        logging.info("Applying loaded layout...");
        try:
            self.reset_zoom() # Reset zoom first
            draggable_items = self.canvas.find_withtag("draggable");
            for item_id in draggable_items:
                if self.canvas.find_withtag(item_id): self.canvas.delete(item_id)
            self.images.clear(); self.tk_images.clear(); self.pasted_overlay_pil_image=None; self.pasted_overlay_tk_image=None; self.pasted_overlay_item_id=None; self.pasted_overlay_offset=(0,0); self.last_clicked_item_id=None; self.selected_item_ids.clear();
            if hasattr(self.interaction_handler, 'clear_selection_visuals'): self.interaction_handler.clear_selection_visuals()
            bg_hex = settings_data.get("background_color"); grid_name = settings_data.get("selected_grid", "None"); snap = settings_data.get("snap_enabled", True); overlap = settings_data.get("overlap_enabled", True)
            if bg_hex: self.set_background_color(bg_hex)
            else: self.background_color = None
            self.snap_enabled.set(snap); self.overlap_enabled.set(overlap); # Apply overlap
            self.last_capture_origin = tuple(capture_origin) if capture_origin and len(capture_origin) == 2 else None # Store origin
            self.app.selected_grid.set(grid_name); self.app.on_grid_selected() # Apply grid
            for item_info in items_to_place:
                pil_img=item_info.get('pil_image'); fp=item_info.get('filepath'); x=item_info.get('x'); y=item_info.get('y')
                if pil_img and fp and isinstance(x,(int,float)) and isinstance(y,(int,float)): self.add_image(pil_img, fp, int(round(x)), int(round(y))) # Add image handles current scale
            if overlay_data and isinstance(overlay_data.get('x'),(int,float)) and isinstance(overlay_data.get('y'),(int,float)): self.pasted_overlay_offset = (int(round(overlay_data['x'])), int(round(overlay_data['y']))); logging.info(f"Stored overlay offset from layout: {self.pasted_overlay_offset}")
            else: self.pasted_overlay_offset = (0, 0)
            logging.info("Layout apply finished.")
        except Exception as e: logging.error(f"Error applying layout: {e}", exc_info=True); messagebox.showerror("Load Error", f"Failed to apply layout.\n{e}")

    # *** MODIFIED: Center view on content TOP-LEFT ***
    def center_view_on_content(self, event=None):
        """Moves the view so the top-left of content bbox is near canvas top-left."""
        logging.debug("Centering view on content top-left.")
        try:
             # Use canvas.bbox("draggable") to get bbox in *current* canvas coordinates
             bbox = self.canvas.bbox("draggable")
             if not bbox: logging.debug("Cannot center view: No items found."); return

             content_tl_x, content_tl_y = bbox[0], bbox[1] # Top-left of content bbox (in current canvas coords)

             # Get current top-left canvas coordinate visible in the view
             view_tl_x = self.canvas.canvasx(0)
             view_tl_y = self.canvas.canvasy(0)

             # Calculate delta needed to move view's top-left TO the content's top-left
             padding = 10 # Add small padding in canvas units
             delta_x = (content_tl_x - padding) - view_tl_x
             delta_y = (content_tl_y - padding) - view_tl_y

             # Scroll the canvas view by the delta
             self.canvas.xview_scroll(int(round(delta_x)), "units")
             self.canvas.yview_scroll(int(round(delta_y)), "units")

             logging.info(f"Centered view TL. Scrolled view by ({delta_x:.1f}, {delta_y:.1f}) canvas units.")
             self.draw_grid() # Redraw grid after panning
             if hasattr(self.interaction_handler,'_update_selection_visual_positions'): self.interaction_handler._update_selection_visual_positions()

        except Exception as e: logging.error(f"Error centering view: {e}", exc_info=True)

    # --- Other Methods ---
    def select_image(self, index): logging.warning("CanvasWindow.select_image(index) not implemented.")