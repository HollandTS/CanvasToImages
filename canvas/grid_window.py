def _handle_item_drag(self, event, filepath, item_frame):
    """Initiate or update drag operation."""
    if self.drag_data["filepath"] == filepath:
        if not self.drag_data["toplevel"]:
            # Create Toplevel only if mouse moved enough
            if abs(event.x_root - self.drag_data["x"]) > 5 or abs(event.y_root - self.drag_data["y"]) > 5:
                logging.debug(f"Drag Start: Creating Toplevel for selected items")
                try:
                    if not self.app or not self.app.root or not self.app.root.winfo_exists(): 
                        logging.error("Drag Start failed: Root missing.")
                        return
                    
                    # If the dragged item is not in selected_paths, clear selection and select only this item
                    if filepath not in self.selected_paths:
                        self.selected_paths.clear()
                        self.selected_paths.add(filepath)
                        self._update_all_item_visuals()
                    
                    # Create a toplevel window for each selected item
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
                        offset += 10  # Offset each thumbnail slightly for visibility
                except Exception as e:
                    logging.error(f"Error creating drag toplevels: {e}", exc_info=True)
                    for toplevel in self.drag_data.get("toplevels", []):
                        if toplevel and toplevel.winfo_exists():
                            toplevel.destroy()
                    self.drag_data["toplevels"] = []
        elif self.drag_data.get("toplevels"):
            try:
                # Update position of all toplevel windows
                offset = 0
                for toplevel in self.drag_data["toplevels"]:
                    if toplevel.winfo_exists():
                        toplevel.geometry(f"+{event.x_root + 5 + offset}+{event.y_root + 5 + offset}")
                        offset += 10
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
                
                # Drop all selected items with slight offset
                offset = 0
                for filepath in self.selected_paths:
                    logging.info(f"Item '{os.path.basename(filepath)}' dropped on canvas.")
                    pil_image = self.images_data[filepath].get('pil_image')
                    if pil_image:
                        self.app.canvas_window.add_image(pil_image, filepath, 
                                                       canvas_x + offset, canvas_y + offset)
                        if hasattr(self.app, 'add_to_filelist'):
                            self.app.add_to_filelist(filepath)
                        offset += 20  # Offset each dropped image slightly
                    else:
                        logging.error(f"Cannot drop: PIL image missing for {filepath}")
            else:
                logging.debug("Items released outside main canvas.")
        except Exception as e:
            logging.error(f"Error processing drop: {e}", exc_info=True) 