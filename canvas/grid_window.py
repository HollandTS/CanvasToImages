def _handle_item_drag(self, event, filepath, item_frame):
    """Initiate or update drag operation."""
    ctrl_or_shift = (event.state & 0x0004 or event.state & 0x0001)  # 0x0004: Ctrl, 0x0001: Shift
    multi_selected = len(self.selected_paths) > 1
    # If Ctrl/Shift is held and multiple images are selected, drag all selected
    if ctrl_or_shift and multi_selected and filepath in self.selected_paths:
        # Multi-image drag
        if not self.drag_data.get("toplevels"):
            self.drag_data["toplevels"] = []
            offset = 0
            for selected_path in self.selected_paths:
                toplevel = tk.Toplevel(self.app.root)
                toplevel.overrideredirect(True)
                toplevel.attributes("-topmost", True)
                drag_image = self.images_data[selected_path].get('thumb_photo')
                if drag_image:
                    Label(toplevel, image=drag_image, relief="solid", bd=1).pack()
                else:
                    Label(toplevel, text="?", relief="solid", bd=1, bg="yellow").pack()
                toplevel.geometry(f"+{event.x_root + 5 + offset}+{event.y_root + 5 + offset}")
                self.drag_data["toplevels"].append(toplevel)
                offset += 10
        elif self.drag_data.get("toplevels"):
            try:
                offset = 0
                for toplevel in self.drag_data["toplevels"]:
                    if toplevel.winfo_exists():
                        toplevel.geometry(f"+{event.x_root + 5 + offset}+{event.y_root + 5 + offset}")
                        offset += 10
            except tk.TclError:
                self.drag_data["toplevels"] = []
    else:
        # Single-image drag (or no modifier)
        if filepath not in self.selected_paths:
            self.selected_paths.clear()
            self.selected_paths.add(filepath)
            self._update_all_item_visuals()
        if not self.drag_data.get("toplevels"):
            self.drag_data["toplevels"] = []
            drag_image = self.images_data[filepath].get('thumb_photo')
            toplevel = tk.Toplevel(self.app.root)
            toplevel.overrideredirect(True)
            toplevel.attributes("-topmost", True)
            if drag_image:
                Label(toplevel, image=drag_image, relief="solid", bd=1).pack()
            else:
                Label(toplevel, text="?", relief="solid", bd=1, bg="yellow").pack()
            toplevel.geometry(f"+{event.x_root + 5}+{event.y_root + 5}")
            self.drag_data["toplevels"].append(toplevel)
        elif self.drag_data.get("toplevels"):
            try:
                for toplevel in self.drag_data["toplevels"]:
                    if toplevel.winfo_exists():
                        toplevel.geometry(f"+{event.x_root + 5}+{event.y_root + 5}")
            except tk.TclError:
                self.drag_data["toplevels"] = []

def _handle_item_release(self, event):
    """Handle releasing the dragged items."""
    toplevels = self.drag_data.get("toplevels", [])
    dragged_filepath = self.drag_data.get("filepath")
    
    # Clean up toplevel windows
    for toplevel in toplevels:
        try:
            if toplevel.winfo_exists():
                toplevel.destroy()
        except tk.TclError:
            pass
    
    # Reset drag data
    self.drag_data = {"filepath": None, "widget": None, "x":0, "y":0, "toplevel":None, "toplevels":[]}
    
    # Process drops if over canvas
    if dragged_filepath and self.app.canvas_window:
        try:
            if self.app.canvas_window.is_above_canvas(event):
                canvas_widget = self.app.canvas_window.canvas
                canvas_x = event.x_root - canvas_widget.winfo_rootx()
                canvas_y = event.y_root - canvas_widget.winfo_rooty()
                
                # --- Arrange dropped images in a grid ---
                import math
                selected_paths = list(self.selected_paths)
                n = len(selected_paths)
                if n == 0:
                    return
                grid_cols = math.ceil(math.sqrt(n))
                grid_rows = math.ceil(n / grid_cols)
                spacing = 64  # You can adjust this spacing as needed
                for idx, filepath in enumerate(selected_paths):
                    row = idx // grid_cols
                    col = idx % grid_cols
                    x = canvas_x + col * spacing
                    y = canvas_y + row * spacing
                    logging.info(f"Item '{os.path.basename(filepath)}' dropped on canvas at ({x},{y}).")
                    pil_image = self.images_data[filepath].get('pil_image')
                    if pil_image:
                        self.app.canvas_window.add_image(pil_image, filepath, x, y)
                        if hasattr(self.app, 'add_to_filelist'):
                            self.app.add_to_filelist(filepath)
                    else:
                        logging.error(f"Cannot drop: PIL image missing for {filepath}")
            else:
                logging.debug("Items released outside main canvas.")
        except Exception as e:
            logging.error(f"Error processing drop: {e}", exc_info=True)