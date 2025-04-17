# --- canvas/handlers/select.py ---
import tkinter as tk
import logging
import sys

class SelectHandler:
    """Handles selection state UPDATE and Box Select drawing."""
    def __init__(self, canvas_view, interaction_handler):
        self.view = canvas_view
        self.interaction_handler = interaction_handler # To access selection visuals etc.
        self.box_select_data = {"start_x": 0, "start_y": 0, "rect_id": None} # Use WINDOW coords for box drawing

    def handle_click(self, event, clicked_item_id):
        """Handles plain Button-1 click - updates selection state in view."""
        view = self.view
        # This method is called by the main interaction handler AFTER it determines
        # that a plain click happened (no modifiers).
        if clicked_item_id:
            if clicked_item_id not in view.selected_item_ids:
                # If clicking a new item without modifiers, select ONLY this item.
                self.interaction_handler.clear_selection_visuals()
                view.selected_item_ids.clear()
                view.selected_item_ids.add(clicked_item_id)
                self.interaction_handler._add_selection_visual(clicked_item_id)
                logging.debug(f"Select Handler: Single selection set to {clicked_item_id}")
            # else: Clicking an already selected item without modifiers does nothing to selection here.
        else:
            # Clicking empty space without modifiers clears selection.
            self.interaction_handler.clear_selection_visuals()
            view.selected_item_ids.clear()
            logging.debug("Select Handler: Empty click, selection cleared.")

    def handle_ctrl_click(self, event, clicked_item_id):
        """Handles Ctrl/Cmd click - Toggles selection state in the view."""
        # (Logic remains the same)
        view = self.view
        if clicked_item_id:
            if clicked_item_id in view.selected_item_ids:
                if len(view.selected_item_ids) > 1: view.selected_item_ids.remove(clicked_item_id); self.interaction_handler._remove_selection_visual(clicked_item_id); logging.debug(f"Select Handler: Ctrl Deselected {clicked_item_id}")
                else: logging.debug("Select Handler: Ctrl-click ignored (last item)")
            else: view.selected_item_ids.add(clicked_item_id); self.interaction_handler._add_selection_visual(clicked_item_id); logging.debug(f"Select Handler: Ctrl Selected {clicked_item_id}")

    def handle_shift_click(self, event, clicked_item_id):
         # (Remains the same - NYI)
         logging.warning("Shift-click range select NYI.");
         self.handle_ctrl_click(event, clicked_item_id) # Fallback

    # --- Box Select (Use Window Coords for drawing rectangle) ---
    def start_box_select(self, event):
        view = self.view; self.interaction_handler.clear_selection_visuals(); view.selected_item_ids.clear(); view.last_clicked_item_id = None
        # Store WINDOW coordinates for drawing the box
        self.box_select_data["start_x"] = event.x; self.box_select_data["start_y"] = event.y
        # Create rectangle using WINDOW coordinates
        self.box_select_data["rect_id"] = view.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="blue", width=1, dash=(4, 2), tags="selection_box")
        logging.debug(f"Select Handler: Box Start @ window ({event.x},{event.y})")

    def update_box_select(self, event):
        view = self.view; rect_id = self.box_select_data.get("rect_id")
        # Update drawing rectangle using WINDOW coordinates
        if rect_id and view.canvas.find_withtag(rect_id): view.canvas.coords(rect_id, self.box_select_data["start_x"], self.box_select_data["start_y"], event.x, event.y)

    def end_box_select(self, event):
        view = self.view; rect_id = self.box_select_data.get("rect_id"); logging.debug("Select Handler: Box End.")
        if rect_id and view.canvas.find_withtag(rect_id):
            # Get final box corners in WINDOW coordinates
            x1_win=min(self.box_select_data["start_x"],event.x); y1_win=min(self.box_select_data["start_y"],event.y); x2_win=max(self.box_select_data["start_x"],event.x); y2_win=max(self.box_select_data["start_y"],event.y)
            view.canvas.delete(rect_id) # Delete visual box
            # Convert WINDOW coords to CANVAS coords for find_enclosed
            x1_canv = view.canvas.canvasx(x1_win); y1_canv = view.canvas.canvasy(y1_win)
            x2_canv = view.canvas.canvasx(x2_win); y2_canv = view.canvas.canvasy(y2_win)
            # Find items enclosed by CANVAS coordinates
            selected_ids_in_box = view.canvas.find_enclosed(x1_canv, y1_canv, x2_canv, y2_canv)
            newly_selected = set();
            for item_id in selected_ids_in_box:
                 tags = view.canvas.gettags(item_id)
                 if "draggable" in tags: newly_selected.add(item_id)
            view.selected_item_ids = newly_selected # Set selection
            self.interaction_handler.update_selection_visuals() # Update outlines
            logging.info(f"Select Handler: Box selected {len(view.selected_item_ids)} items.")
        self.box_select_data = {"start_x": 0, "start_y": 0, "rect_id": None} # Reset