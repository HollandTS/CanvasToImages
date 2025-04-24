import tkinter as tk
from tkinter import ttk
import logging
import os

class LayersWindow(tk.Toplevel):
    def __init__(self, parent, canvas_window):
        super().__init__(parent)
        self.title("Layers")
        self.canvas_window = canvas_window
        
        # Configure window
        self.geometry("200x400")
        self.minsize(200, 300)
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.withdraw()  # Start hidden
        
        # Create main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create buttons frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(0, 5))
        
        # Create layer movement buttons
        ttk.Button(btn_frame, text="⭱", width=3, command=self.move_to_top).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="↑", width=3, command=self.move_up).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="↓", width=3, command=self.move_down).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="⭳", width=3, command=self.move_to_bottom).pack(side="left", padx=2)
        
        # Create listbox with scrollbar
        self.listbox_frame = ttk.Frame(main_frame)
        self.listbox_frame.pack(fill="both", expand=True)
        
        # Create listbox with extended selection mode
        self.listbox = tk.Listbox(self.listbox_frame, selectmode="extended")
        self.listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(self.listbox_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        # Bind events
        self.listbox.bind('<<ListboxSelect>>', self.on_select)
        self.listbox.bind('<Button-1>', self.on_click)
        self.listbox.bind('<B1-Motion>', self.on_drag_motion)
        self.listbox.bind('<ButtonRelease-1>', self.on_drag_end)
        
        # Store layer information for quick lookup
        self.layer_info = {}  # Maps display_name to (filename, data)
        self.drag_data = {"items": None, "indices": None}
    
    def show(self):
        """Show the window and refresh layers."""
        self.deiconify()
        self.refresh_layers()
    
    def hide(self):
        """Hide the window."""
        self.withdraw()
    
    def refresh_layers(self):
        """Update the listbox with current layers."""
        try:
            self.listbox.delete(0, tk.END)
            self.layer_info.clear()
            
            # Get all images with their z-index
            layers = []
            for filename, data in self.canvas_window.images.items():
                z_index = data.get('z_index', 0)
                display_name = os.path.basename(filename)
                layers.append((z_index, display_name, filename, data))
            
            # Sort by z-index (highest to lowest)
            layers.sort(key=lambda x: x[0], reverse=True)
            
            # Add to listbox and update layer info
            for _, display_name, filename, data in layers:
                self.listbox.insert(tk.END, display_name)
                self.layer_info[display_name] = (filename, data)
            
            # Add overlay if it exists
            if self.canvas_window.pasted_overlay_pil_image:
                overlay_position = self.listbox.size() if self.canvas_window.layer_behind else 0
                self.listbox.insert(overlay_position, "Overlay")
        
        except Exception as e:
            logging.error(f"Error refreshing layers: {e}", exc_info=True)
    
    def on_select(self, event):
        """Handle layer selection."""
        try:
            if not self.listbox.curselection():
                return
            
            # Clear previous canvas selection
            self.canvas_window.selected_item_ids.clear()
            
            # Handle multiple selections
            for index in self.listbox.curselection():
                display_name = self.listbox.get(index)
                if display_name == "Overlay":
                    continue
                
                # Get item info from our lookup dictionary
                if display_name in self.layer_info:
                    _, data = self.layer_info[display_name]
                    item_id = data['id']
                    self.canvas_window.selected_item_ids.add(item_id)
                    self.canvas_window.last_clicked_item_id = item_id
            
            # Update selection visuals
            self.canvas_window.interaction_handler.update_selection_visuals()
        
        except Exception as e:
            logging.error(f"Error handling layer selection: {e}", exc_info=True)
    
    def on_click(self, event):
        """Handle click and start drag if needed."""
        try:
            index = self.listbox.nearest(event.y)
            if index < 0:
                return
            
            # If Control is not held, clear other selections
            if not (event.state & 0x4):  # 0x4 is the Control key state
                self.listbox.selection_clear(0, tk.END)
            
            self.listbox.selection_set(index)
            self.listbox.event_generate('<<ListboxSelect>>')  # Trigger selection event
            
            # Store drag data
            self.drag_data["items"] = [self.listbox.get(i) for i in self.listbox.curselection()]
            self.drag_data["indices"] = list(self.listbox.curselection())
        
        except Exception as e:
            logging.error(f"Error handling click: {e}", exc_info=True)
    
    def on_drag_motion(self, event):
        """Handle drag motion for multiple items."""
        try:
            if not self.drag_data["items"]:
                return
            
            new_index = self.listbox.nearest(event.y)
            if new_index < 0:
                return
            
            old_indices = self.drag_data["indices"]
            if not old_indices:
                return
            
            if new_index != old_indices[0]:
                items = self.drag_data["items"]
                for i in reversed(old_indices):
                    self.listbox.delete(i)
                
                for item in items:
                    self.listbox.insert(new_index, item)
                
                # Update selection
                start_idx = new_index
                end_idx = new_index + len(items) - 1
                self.listbox.selection_clear(0, tk.END)
                for i in range(start_idx, end_idx + 1):
                    self.listbox.selection_set(i)
                
                self.drag_data["indices"] = list(range(start_idx, end_idx + 1))
        
        except Exception as e:
            logging.error(f"Error during drag: {e}", exc_info=True)
    
    def on_drag_end(self, event):
        """End drag operation and update z-indices."""
        try:
            if not self.drag_data["items"]:
                return
            
            # Update z-indices based on new order
            items = list(self.listbox.get(0, tk.END))
            z_index = len(items)
            
            for display_name in items:
                if display_name == "Overlay":
                    self.canvas_window.layer_behind = (z_index == 1)
                elif display_name in self.layer_info:
                    _, data = self.layer_info[display_name]
                    data['z_index'] = z_index
                z_index -= 1
            
            # Clear drag data
            self.drag_data["items"] = None
            self.drag_data["indices"] = None
            
            # Redraw canvas with new order
            self.canvas_window.redraw_canvas()
        
        except Exception as e:
            logging.error(f"Error ending drag: {e}", exc_info=True)
    
    def move_to_top(self):
        """Move selected layers to top."""
        try:
            if not self.listbox.curselection():
                return
            
            selected_indices = list(self.listbox.curselection())
            selected_items = [self.listbox.get(i) for i in selected_indices]
            
            # Remove selected items
            for i in reversed(selected_indices):
                self.listbox.delete(i)
            
            # Insert all items at the top
            for item in reversed(selected_items):
                self.listbox.insert(0, item)
            
            # Update selection
            self.listbox.selection_clear(0, tk.END)
            for i in range(len(selected_items)):
                self.listbox.selection_set(i)
            
            self.on_drag_end(None)
        
        except Exception as e:
            logging.error(f"Error moving layers to top: {e}", exc_info=True)
    
    def move_up(self):
        """Move selected layers up one position."""
        try:
            if not self.listbox.curselection():
                return
            
            selected_indices = list(self.listbox.curselection())
            if not selected_indices or selected_indices[0] <= 0:
                return
            
            # Move each selected item up one position
            for i in selected_indices:
                item = self.listbox.get(i)
                self.listbox.delete(i)
                self.listbox.insert(i - 1, item)
                self.listbox.selection_set(i - 1)
            
            self.on_drag_end(None)
        
        except Exception as e:
            logging.error(f"Error moving layers up: {e}", exc_info=True)
    
    def move_down(self):
        """Move selected layers down one position."""
        try:
            if not self.listbox.curselection():
                return
            
            selected_indices = list(self.listbox.curselection())
            if not selected_indices or selected_indices[-1] >= self.listbox.size() - 1:
                return
            
            # Move each selected item down one position (process in reverse to maintain order)
            for i in reversed(selected_indices):
                item = self.listbox.get(i)
                self.listbox.delete(i)
                self.listbox.insert(i + 1, item)
                self.listbox.selection_set(i + 1)
            
            self.on_drag_end(None)
        
        except Exception as e:
            logging.error(f"Error moving layers down: {e}", exc_info=True)
    
    def move_to_bottom(self):
        """Move selected layers to bottom."""
        try:
            if not self.listbox.curselection():
                return
            
            selected_indices = list(self.listbox.curselection())
            selected_items = [self.listbox.get(i) for i in selected_indices]
            
            # Remove selected items
            for i in reversed(selected_indices):
                self.listbox.delete(i)
            
            # Insert all items at the bottom
            for item in selected_items:
                self.listbox.insert(tk.END, item)
            
            # Update selection
            self.listbox.selection_clear(0, tk.END)
            last_index = self.listbox.size() - 1
            for i in range(len(selected_items)):
                self.listbox.selection_set(last_index - i)
            
            self.on_drag_end(None)
        
        except Exception as e:
            logging.error(f"Error moving layers to bottom: {e}", exc_info=True) 