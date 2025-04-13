# --- canvas/handlers/interaction.py ---
import tkinter as tk
import logging
import math
import sys

class InteractionHandler:
    def __init__(self, canvas_view):
        self.view = canvas_view
        # Dragging single/multi items - store CANVAS start coords
        self.drag_data = {"item": None, "canvas_x": 0, "canvas_y": 0}
        self.multi_drag_data = {"active": False, "start_x": 0, "start_y": 0, "item_start_coords": {}}
        # Box selection - store CANVAS start coords
        self.box_select_data = {"start_x": 0, "start_y": 0, "rect_id": None}
        self.selection_outline_ids = {}
        # Panning State - Store last WINDOW coords for pan delta
        self.pan_data = {"active": False, "last_x": 0, "last_y": 0}

    # --- Click Handlers ---
    def handle_click(self, event):
        # Ignore click if panning is active
        if self.pan_data.get("active"): return
        view = self.view; view.last_clicked_item_id = None; canvas_x = view.canvas.canvasx(event.x); canvas_y = view.canvas.canvasy(event.y); clicked_item_id = self._find_draggable_item_canvas(canvas_x, canvas_y)
        if view.app.selecting_bg_color:
            if clicked_item_id and "pasted_overlay" not in view.canvas.gettags(clicked_item_id):
                 if hasattr(view,'bg_handler') and hasattr(view.bg_handler,'handle_pick_click'): view.bg_handler.handle_pick_click(event)
                 else: logging.error("BG Pick Error: bg_handler missing."); view.app.cancel_select_background_color()
            else: logging.info("BG Pick click missed tile."); view.app.cancel_select_background_color()
            return
        ctrl=(event.state & 0x0004)!=0 or (sys.platform=="darwin" and (event.state & 0x0008)!=0); shift=(event.state & 0x0001)!=0; mod = ctrl or shift
        if clicked_item_id:
            view.last_clicked_item_id = clicked_item_id
            if not mod and clicked_item_id not in view.selected_item_ids: self.clear_selection_visuals(); view.selected_item_ids.clear(); view.selected_item_ids.add(clicked_item_id); self._add_selection_visual(clicked_item_id)
            self._prepare_drag(event, clicked_item_id, canvas_x, canvas_y) # Prepare drag based on current selection
        else:
            if not mod: self.clear_selection_visuals(); view.selected_item_ids.clear()
            self._reset_drag_state() # Reset item drag state

    def handle_ctrl_click(self, event):
        if self.pan_data.get("active"): return
        view = self.view; canvas_x = view.canvas.canvasx(event.x); canvas_y = view.canvas.canvasy(event.y); clicked_item_id = self._find_draggable_item_canvas(canvas_x, canvas_y)
        if clicked_item_id:
            view.last_clicked_item_id = clicked_item_id
            if clicked_item_id in view.selected_item_ids:
                 if len(view.selected_item_ids)>1: view.selected_item_ids.remove(clicked_item_id); self._remove_selection_visual(clicked_item_id)
            else: view.selected_item_ids.add(clicked_item_id); self._add_selection_visual(clicked_item_id)
            self._reset_drag_state()
        else: self._reset_drag_state()

    def handle_shift_click(self, event): logging.warning("Shift-click range select NYI."); self.handle_ctrl_click(event)

    # --- Drag Handlers ---
    def _prepare_drag(self, event, clicked_item_id, click_canvas_x, click_canvas_y):
         view = self.view
         if clicked_item_id in view.selected_item_ids: # Prep Multi-Drag
             self.multi_drag_data={"active":True, "start_x":click_canvas_x, "start_y":click_canvas_y, "item_start_coords":{}}
             for item_id in view.selected_item_ids: coords=view.canvas.coords(item_id);
             if coords: self.multi_drag_data["item_start_coords"][item_id] = coords
             logging.debug(f"Prep multi-drag {len(view.selected_item_ids)}."); self.drag_data["item"] = None
         else: # Prep Single Drag
             self.drag_data={"item":clicked_item_id, "canvas_x":click_canvas_x, "canvas_y":click_canvas_y} # Only store canvas coords
             self.multi_drag_data["active"] = False; logging.debug(f"Prep single drag {clicked_item_id}.")

    def handle_drag(self, event):
        # Ignore B1 drag if panning
        if self.pan_data.get("active"): return
        view = self.view
        try:
            current_canvas_x = view.canvas.canvasx(event.x); current_canvas_y = view.canvas.canvasy(event.y)
            if self.multi_drag_data.get("active"):
                delta_x = current_canvas_x - self.multi_drag_data["start_x"]; delta_y = current_canvas_y - self.multi_drag_data["start_y"]
                for item_id, start_coords in self.multi_drag_data["item_start_coords"].items():
                    if view.canvas.find_withtag(item_id): target_x = start_coords[0] + delta_x; target_y = start_coords[1] + delta_y; view.canvas.coords(item_id, target_x, target_y); self._update_item_stored_coords(item_id, round(target_x), round(target_y))
                self._update_selection_visual_positions()
            elif self.drag_data.get("item"):
                item_id = self.drag_data["item"]
                if not view.canvas.find_withtag(item_id): self.drag_data["item"]=None; return
                delta_x = current_canvas_x - self.drag_data["canvas_x"]; delta_y = current_canvas_y - self.drag_data["canvas_y"]
                if abs(delta_x) > 0.001 or abs(delta_y) > 0.001: view.canvas.move(item_id, delta_x, delta_y)
                self.drag_data["canvas_x"] = current_canvas_x; self.drag_data["canvas_y"] = current_canvas_y # Update last canvas pos
                new_coords = view.canvas.coords(item_id)
                if new_coords: new_x = round(new_coords[0]); new_y = round(new_coords[1]); self._update_item_stored_coords(item_id, new_x, new_y); self._update_single_selection_visual_position(item_id)
        except Exception as e: logging.error(f"Int Drag Error: {e}", exc_info=True); self._reset_drag_state()

    def handle_release(self, event):
        # Ignore B1 release if panning
        if self.pan_data.get("active"): return
        view = self.view
        try:
            items_affected = []; final_coords_map = {}
            if self.multi_drag_data.get("active"): items_affected = list(self.multi_drag_data["item_start_coords"].keys())
            elif self.drag_data.get("item"): items_affected = [self.drag_data["item"]]
            if items_affected:
                logging.debug(f"Release affecting {len(items_affected)}.")
                if not view.overlap_enabled.get():
                    all_item_ids=set(view.canvas.find_withtag("draggable"));
                    if view.pasted_overlay_item_id: all_item_ids.add(view.pasted_overlay_item_id)
                    for moved_id in items_affected:
                         if view.canvas.find_withtag(moved_id): self._resolve_overlaps(moved_id, all_item_ids - {moved_id})
                if view.snap_enabled.get() and view.current_grid_info:
                    for item_id in items_affected:
                        if view.canvas.find_withtag(item_id): self.snap_to_grid(item_id)
                for item_id in items_affected:
                     if view.canvas.find_withtag(item_id):
                         fc = view.canvas.coords(item_id);
                         if fc: fx=int(round(fc[0])); fy=int(round(fc[1])); final_coords_map[item_id]=(fx,fy); self._update_item_stored_coords(item_id,fx,fy)
                self._update_selection_visual_positions()
            for item_id, pos in final_coords_map.items(): logging.info(f"Final pos Item {item_id}: ({pos[0]},{pos[1]})")
        except Exception as e: logging.error(f"Int Release Error: {e}", exc_info=True)
        finally: self._reset_drag_state() # Reset item drag, not pan

    # --- Overlap Resolution ---
    def _resolve_overlaps(self, moved_item_id, other_item_ids):
        view = self.view; moved_bbox = view.canvas.bbox(moved_item_id);
        if not moved_bbox: return
        mx1, my1, mx2, my2 = moved_bbox
        for other_item_id in other_item_ids:
            if not view.canvas.find_withtag(other_item_id): continue
            other_bbox = view.canvas.bbox(other_item_id);
            if not other_bbox: continue
            ox1, oy1, ox2, oy2 = other_bbox
            is_overlapping = not (mx2 <= ox1 or mx1 >= ox2 or my2 <= oy1 or my1 >= oy2)
            if is_overlapping:
                logging.debug(f"Overlap: {moved_item_id} vs {other_item_id}")
                push_right=(ox2-mx1)+1; push_left=(ox1-mx2)-1; push_down=(oy2-my1)+1; push_up=(oy1-my2)-1
                pushes = [];
                if push_right>0: pushes.append((push_right,0));
                if push_left<0: pushes.append((push_left,0));
                if push_down>0: pushes.append((0,push_down));
                if push_up<0: pushes.append((0,push_up));
                if not pushes: continue
                min_push_dist_sq = float('inf'); best_push = (0,0)
                for dx, dy in pushes: dist_sq = dx*dx+dy*dy;
                if dist_sq < min_push_dist_sq: min_push_dist_sq=dist_sq; best_push=(dx,dy)
                push_dx, push_dy = best_push
                if push_dx != 0 or push_dy != 0:
                    logging.info(f"Resolving overlap {moved_item_id} push ({push_dx:.0f},{push_dy:.0f})")
                    view.canvas.move(moved_item_id, push_dx, push_dy)
                    moved_bbox = view.canvas.bbox(moved_item_id);
                    if not moved_bbox: logging.error("Item vanished!"); return
                    mx1, my1, mx2, my2 = moved_bbox

    # --- Box/Marquee Selection ---
    def start_box_select(self, event):
        if self.pan_data.get("active") or self.drag_data.get("item") or self.multi_drag_data.get("active"): return
        view = self.view; self.clear_selection_visuals(); view.selected_item_ids.clear()
        canvas_x = view.canvas.canvasx(event.x); canvas_y = view.canvas.canvasy(event.y)
        self.box_select_data = {"start_x": canvas_x, "start_y": canvas_y}
        self.box_select_data["rect_id"] = view.canvas.create_rectangle(canvas_x, canvas_y, canvas_x, canvas_y, outline="blue", width=1, dash=(4, 2), tags="selection_box")
    def update_box_select(self, event):
        view = self.view; rect_id = self.box_select_data.get("rect_id")
        if rect_id and view.canvas.find_withtag(rect_id):
            cx = view.canvas.canvasx(event.x); cy = view.canvas.canvasy(event.y)
            view.canvas.coords(rect_id, self.box_select_data["start_x"], self.box_select_data["start_y"], cx, cy)
    def end_box_select(self, event):
        view = self.view; rect_id = self.box_select_data.get("rect_id");
        if rect_id and view.canvas.find_withtag(rect_id):
            sx=self.box_select_data["start_x"]; sy=self.box_select_data["start_y"]; ex=view.canvas.canvasx(event.x); ey=view.canvas.canvasy(event.y)
            x1=min(sx,ex); y1=min(sy,ey); x2=max(sx,ex); y2=max(sy,ey)
            view.canvas.delete(rect_id)
            selected_ids = view.canvas.find_enclosed(x1, y1, x2, y2)
            view.selected_item_ids = {item_id for item_id in selected_ids if "draggable" in view.canvas.gettags(item_id)}
            self.update_selection_visuals()
            logging.info(f"Box selected {len(view.selected_item_ids)} items.")
        self.box_select_data = {"start_x": 0, "start_y": 0, "rect_id": None}

    # --- Selection Visuals ---
    def _add_selection_visual(self, item_id):
        view=self.view;
        if item_id in self.selection_outline_ids: return
        bbox=view.canvas.bbox(item_id);
        if bbox: x1,y1,x2,y2=bbox;
        if x2-x1>=1 and y2-y1>=1: outline_id=view.canvas.create_rectangle(x1,y1,x2,y2,outline="green",width=1,tags=("selection_outline",f"outline_{item_id}")); self.selection_outline_ids[item_id]=outline_id; view.canvas.tag_raise(outline_id)
    def _remove_selection_visual(self, item_id):
         view = self.view; outline_id = self.selection_outline_ids.pop(item_id, None);
         if outline_id and view.canvas.find_withtag(outline_id): view.canvas.delete(outline_id)
    def update_selection_visuals(self):
         view=self.view; current=set(self.selection_outline_ids.keys()); selected=view.selected_item_ids
         for item_id in (current-selected): self._remove_selection_visual(item_id)
         for item_id in (selected-current):
             if view.canvas.find_withtag(item_id): self._add_selection_visual(item_id)
             elif item_id in view.selected_item_ids: view.selected_item_ids.remove(item_id)
    def _update_selection_visual_positions(self):
         view=self.view;
         for item_id, outline_id in self.selection_outline_ids.items():
             if view.canvas.find_withtag(item_id) and view.canvas.find_withtag(outline_id):
                 bbox = view.canvas.bbox(item_id);
                 if bbox: view.canvas.coords(outline_id, bbox[0], bbox[1], bbox[2], bbox[3])
    def clear_selection_visuals(self):
        view=self.view;
        for outline_id in list(self.selection_outline_ids.values()):
             if view.canvas.find_withtag(outline_id): view.canvas.delete(outline_id)
        self.selection_outline_ids.clear()

    # --- Snapping Logic ---
    def snap_to_grid(self, item_id):
        # (Remains the same)
        view=self.view; grid_info=view.current_grid_info;
        if not grid_info: return
        grid_type=grid_info.get("type")
        try:
            current_coords = view.canvas.coords(item_id);
            if not current_coords: return
            current_x, current_y = current_coords
            ideal_snap_x, ideal_snap_y = current_x, current_y
            if grid_type == "pixel":
                step = grid_info.get("step");
                if step and step > 0: ideal_snap_x = round(current_x/step)*step; ideal_snap_y = round(current_y/step)*step
                else: return
            elif grid_type == "diamond":
                cell_w=grid_info.get("cell_width"); cell_h=grid_info.get("cell_height");
                if cell_w and cell_w>0 and cell_h and cell_h>0:
                    if cell_w==0 or cell_h==0: return
                    grid_u=(current_y/cell_h)+(current_x/cell_w); grid_v=(current_y/cell_h)-(current_x/cell_w)
                    nearest_u=round(grid_u); nearest_v=round(grid_v)
                    ideal_snap_x=(nearest_u-nearest_v)*cell_w/2.0; ideal_snap_y=(nearest_u+nearest_v)*cell_h/2.0
                else: return
            else: return
            final_snap_x=int(round(ideal_snap_x)); final_snap_y=int(round(ideal_snap_y))
            delta_x=final_snap_x-int(round(current_x)); delta_y=final_snap_y-int(round(current_y))
            if delta_x != 0 or delta_y != 0:
                logging.info(f"Snapping Item {item_id} to int pos ({final_snap_x},{final_snap_y})")
                view.canvas.move(item_id, delta_x, delta_y)
                self._update_item_stored_coords(item_id, final_snap_x, final_snap_y)
            else:
                logging.debug(f"Item {item_id} already snapped int pos ({final_snap_x},{final_snap_y}).")
                self._update_item_stored_coords(item_id, final_snap_x, final_snap_y)
        except Exception as e: logging.error(f"Snap Error item {item_id}, type {grid_type}: {e}", exc_info=True)


    # *** Panning Handlers using canvas.scan_dragto for smoother pixel panning ***
    def handle_pan_start(self, event):
        """Records starting position for panning if no drag/select is active."""
        if self.drag_data.get("item") or self.multi_drag_data.get("active") or self.box_select_data.get("rect_id"):
            logging.debug("Pan Start ignored: Drag/Select active.")
            return
        # *** Use scan_mark for panning start ***
        self.view.canvas.scan_mark(event.x, event.y)
        self.pan_data["active"] = True
        # Store last window coords if needed elsewhere, but not strictly needed for scan_dragto
        self.pan_data["last_x"] = event.x
        self.pan_data["last_y"] = event.y
        self.view.canvas.config(cursor="fleur")
        logging.debug(f"Pan Start (scan_mark) at window ({event.x},{event.y})")

    def handle_pan_motion(self, event):
        """Moves the canvas view based on middle mouse drag using scan_dragto."""
        if self.pan_data.get("active"):
            # *** Use scan_dragto ***
            # Gain = 1 means 1:1 pixel movement relative to scan_mark point
            # Gain < 1 means slower movement (e.g., 0.5 means half speed)
            # Gain > 1 means faster movement
            # Since you want very slow, gain=1 (the default if omitted) might still
            # feel fast if the system sends many events.
            # Let's use gain=1 for now, assuming the issue was using "units".
            self.view.canvas.scan_dragto(event.x, event.y, gain=1)

            # --- Optional: Redraw grid/visuals during pan ---
            # Redrawing during scan_dragto can sometimes cause flicker or lag.
            # Test performance; if laggy, move these to handle_pan_end.
            self.view.draw_grid()
            self._update_selection_visual_positions()
            # No need to update last_x/y here, scan_mark is the reference

    def handle_pan_end(self, event):
        """Resets panning state."""
        if self.pan_data.get("active"):
             self.pan_data["active"] = False
             self.view.canvas.config(cursor="")
             # Final redraw if not done during motion
             # self.view.draw_grid()
             # self._update_selection_visual_positions()
             logging.debug("Pan End")
    # ****************************

    # --- Helper Methods ---
    def _find_draggable_item_canvas(self, canvas_x, canvas_y): # Find based on canvas coords
        view = self.view; item_ids = view.canvas.find_overlapping(canvas_x-1, canvas_y-1, canvas_x+1, canvas_y+1)
        for item_id in reversed(item_ids):
            if "draggable" in view.canvas.gettags(item_id): return item_id
        return None
    def _reset_drag_state(self):
         self.drag_data = {"item": None, "canvas_x": 0, "canvas_y": 0}
         self.multi_drag_data = {"active": False, "start_x": 0, "start_y": 0, "item_start_coords": {}}
         # DO NOT reset pan_data here
    def _update_item_stored_coords(self, item_id, new_x, new_y):
         view = self.view; int_x = int(round(new_x)); int_y = int(round(new_y))
         if item_id == view.pasted_overlay_item_id:
             if view.pasted_overlay_offset != (int_x, int_y): view.pasted_overlay_offset = (int_x, int_y)
         else: # Tile
             tags=view.canvas.gettags(item_id);
             if tags and len(tags)>1 and "pasted_overlay" not in tags:
                 fname=tags[1];
                 if fname in view.images and view.images[fname]['id']==item_id:
                     if view.images[fname]["x"] != int_x or view.images[fname]["y"] != int_y: view.images[fname]["x"]=int_x; view.images[fname]["y"]=int_y;
    def _update_single_selection_visual_position(self, item_id):
        if item_id in self.selection_outline_ids:
             view=self.view; outline_id = self.selection_outline_ids[item_id]
             if view.canvas.find_withtag(item_id) and view.canvas.find_withtag(outline_id):
                 bbox = view.canvas.bbox(item_id);
                 if bbox: x1,y1,x2,y2=bbox;
                 if x2-x1>=1 and y2-y1>=1: view.canvas.coords(outline_id,x1,y1,x2,y2)
                 else: view.canvas.coords(outline_id,-1,-1,-1,-1) # Hide
    def _update_selection_visual_positions(self):
         view=self.view;
         for item_id, outline_id in self.selection_outline_ids.items():
             if view.canvas.find_withtag(item_id) and view.canvas.find_withtag(outline_id):
                 bbox = view.canvas.bbox(item_id);
                 if bbox: view.canvas.coords(outline_id, bbox[0], bbox[1], bbox[2], bbox[3])
    def clear_selection_visuals(self):
        view=self.view;
        for outline_id in list(self.selection_outline_ids.values()):
             if view.canvas.find_withtag(outline_id): view.canvas.delete(outline_id)
        self.selection_outline_ids.clear()