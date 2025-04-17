# --- canvas/handlers/drag.py ---
import tkinter as tk
import logging
import math

class DragHandler:
    """Handles moving single/multiple items, snapping, and overlap."""
    def __init__(self, canvas_view, interaction_handler):
        self.view = canvas_view
        self.interaction_handler = interaction_handler # To access shared drag state and helpers

    def handle_drag(self, event):
        """Handles dragging motion using simple window coordinate delta."""
        view = self.view
        # Get drag state from the main interaction handler
        multi_drag_data = self.interaction_handler.multi_drag_data
        drag_data = self.interaction_handler.drag_data
        try:
            if multi_drag_data.get("active"):
                # --- Drag Multiple ---
                current_x, current_y = event.x, event.y
                delta_x = current_x - multi_drag_data["start_x"]
                delta_y = current_y - multi_drag_data["start_y"]
                for item_id, start_coords in multi_drag_data["item_start_coords"].items():
                    if view.canvas.find_withtag(item_id):
                        target_x = start_coords[0] + delta_x
                        target_y = start_coords[1] + delta_y
                        view.canvas.coords(item_id, target_x, target_y) # Set absolute position
                        # Update stored integer coords immediately via main handler
                        self.interaction_handler._update_item_stored_coords(item_id, round(target_x), round(target_y))
                self.interaction_handler._update_selection_visual_positions() # Move outlines

            elif drag_data.get("item"):
                # --- Drag Single ---
                item_id = drag_data["item"]
                if not view.canvas.find_withtag(item_id): drag_data["item"]=None; return
                # Calculate delta based on WINDOW coordinates stored in drag_data
                delta_x = event.x - drag_data["x"]
                delta_y = event.y - drag_data["y"]
                # Apply delta using canvas.move
                if delta_x != 0 or delta_y != 0:
                    view.canvas.move(item_id, delta_x, delta_y)
                # Update stored WINDOW coordinates for next delta calculation
                drag_data["x"] = event.x
                drag_data["y"] = event.y
                # Update stored ABSOLUTE rounded integer coords
                new_coords = view.canvas.coords(item_id)
                if new_coords:
                    new_x = round(new_coords[0]); new_y = round(new_coords[1])
                    self.interaction_handler._update_item_stored_coords(item_id, new_x, new_y)
                    self.interaction_handler._update_single_selection_visual_position(item_id) # Update outline

        except Exception as e: logging.error(f"Drag Handler Error: {e}", exc_info=True); self.interaction_handler._reset_drag_state()


    def handle_release(self, event):
        """Handles drag release, applying adjustments."""
        # (Logic remains the same as previous version, relies on InteractionHandler state)
        view = self.view
        multi_drag_data = self.interaction_handler.multi_drag_data
        drag_data = self.interaction_handler.drag_data
        try:
            items_affected = []; final_coords_map = {}
            if multi_drag_data.get("active"): items_affected = list(multi_drag_data["item_start_coords"].keys())
            elif drag_data.get("item"): items_affected = [drag_data["item"]]
            if items_affected:
                logging.debug(f"Release affecting {len(items_affected)} items.")
                # 1. Overlaps
                if not view.overlap_enabled.get(): # *** Use view's attribute ***
                    all_item_ids=set(view.canvas.find_withtag("draggable"));
                    if view.pasted_overlay_item_id and view.canvas.find_withtag(view.pasted_overlay_item_id): all_item_ids.add(view.pasted_overlay_item_id)
                    for moved_id in items_affected:
                         if view.canvas.find_withtag(moved_id): self._resolve_overlaps(moved_id, all_item_ids - {moved_id})
                # 2. Snapping
                if view.snap_enabled.get() and view.current_grid_info: # *** Use view's attribute ***
                    for item_id in items_affected:
                        if view.canvas.find_withtag(item_id): self.snap_to_grid(item_id)
                # 3. Store final coords
                for item_id in items_affected:
                     if view.canvas.find_withtag(item_id):
                         fc = view.canvas.coords(item_id);
                         if fc: fx=int(round(fc[0])); fy=int(round(fc[1])); final_coords_map[item_id]=(fx,fy); self.interaction_handler._update_item_stored_coords(item_id,fx,fy)
                # 4. Update visuals
                self.interaction_handler._update_selection_visual_positions()
            for item_id, pos in final_coords_map.items(): logging.info(f"Final pos Item {item_id}: ({pos[0]},{pos[1]})")
        except Exception as e: logging.error(f"Drag Release Error: {e}", exc_info=True)
        finally: self.interaction_handler._reset_drag_state() # Reset in main handler

    def snap_to_grid(self, item_id):
        """Snaps item, ensures integer coords stored."""
        # (Logic remains the same as previous version)
        view=self.view; grid_info=view.current_grid_info;
        if not grid_info: return
        grid_type=grid_info.get("type")
        try:
            current_coords = view.canvas.coords(item_id);
            if not current_coords: return
            current_x, current_y = current_coords
            ideal_snap_x, ideal_snap_y = current_x, current_y
            if grid_type == "pixel":
                step = grid_info.get("step")
                if step and step > 0: ideal_snap_x = round(current_x/step)*step; ideal_snap_y = round(current_y/step)*step
                else: return
            elif grid_type == "diamond":
                cell_w=grid_info.get("cell_width"); cell_h=grid_info.get("cell_height")
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
                view.canvas.move(item_id, delta_x, delta_y)
                self.interaction_handler._update_item_stored_coords(item_id, final_snap_x, final_snap_y) # Update stored state
            else:
                self.interaction_handler._update_item_stored_coords(item_id, final_snap_x, final_snap_y) # Ensure stored state is int
        except Exception as e: logging.error(f"Snap Error item {item_id}, type {grid_type}: {e}", exc_info=True)


    def _resolve_overlaps(self, moved_item_id, other_item_ids):
        """Checks moved item against others, pushes minimally (bbox)."""
        # (Logic remains the same as previous version)
        view = self.view
        if not view.canvas.find_withtag(moved_item_id): return
        moved_bbox = view.canvas.bbox(moved_item_id);
        if not moved_bbox: return
        mx1, my1, mx2, my2 = moved_bbox
        for other_item_id in other_item_ids:
            if not view.canvas.find_withtag(other_item_id): continue
            other_bbox = view.canvas.bbox(other_item_id);
            if not other_bbox: continue
            ox1, oy1, ox2, oy2 = other_bbox
            is_overlapping = not (mx2 <= ox1 or mx1 >= ox2 or my2 <= oy1 or my1 >= oy2)
            if is_overlapping:
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
                    coords_after_push = view.canvas.coords(moved_item_id) # Update stored coords after push
                    if coords_after_push: self.interaction_handler._update_item_stored_coords(moved_item_id, round(coords_after_push[0]), round(coords_after_push[1]))
                    moved_bbox = view.canvas.bbox(moved_item_id); # Update bbox
                    if not moved_bbox: logging.error("Item vanished after overlap push!"); return
                    mx1, my1, mx2, my2 = moved_bbox