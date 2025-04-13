# --- grid_window.py ---
import tkinter as tk
from tkinter import filedialog, Canvas, Frame, Label, Scale, Button, Scrollbar, messagebox
from PIL import Image, ImageTk
import os
import logging
import sys # For platform check

# Check Pillow version for Resampling attribute
try:
    LANCZOS_RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    LANCZOS_RESAMPLE = Image.LANCZOS
    logging.warning("Using older Pillow version's Image.LANCZOS resampling filter.")

# Helper function
def resize_image_keeping_aspect_ratio(image, max_width, max_height):
    """Resizes PIL image preserving aspect ratio."""
    try:
        img_width, img_height = image.size
        if img_width <= 0 or img_height <= 0 or max_width <= 0 or max_height <= 0: return image
        width_ratio = max_width / img_width; height_ratio = max_height / img_height
        resize_ratio = min(width_ratio, height_ratio)
        if abs(resize_ratio - 1.0) > 0.01 :
            new_width = max(1, int(img_width * resize_ratio))
            new_height = max(1, int(img_height * resize_ratio))
            return image.resize((new_width, new_height), LANCZOS_RESAMPLE)
        else: return image
    except Exception as e: logging.error(f"Resize error: {e}", exc_info=True); return image


class GridWindow(tk.Frame):
    def __init__(self, parent, config, app):
        logging.info("Initializing GridWindow (File Panel)")
        super().__init__(parent)
        self.app = app
        self.config = config

        # --- State ---
        self.images_data = {} # {filepath: {'pil_image': pil_img, 'thumb_photo': None, 'item_frame': frame_widget}}
        self.thumb_tk_images = []
        self.sorted_paths = []
        self.selected_paths = set()
        self.last_selected_anchor_path = None
        self.thumbnail_size = tk.IntVar(value=90)
        self.drag_data = {"filepath": None, "widget": None, "x":0, "y":0, "toplevel":None}
        self.fixed_columns = 4 # <<<--- SET FIXED NUMBER OF COLUMNS

        try:
            self._setup_ui()
            self._load_images_from_config()
        except Exception as e:
            logging.error(f"FATAL ERROR during GridWindow UI Setup: {e}", exc_info=True)

    def _setup_ui(self):
        """Creates the UI elements for the file panel."""
        logging.debug("Setting up GridWindow UI")

        # --- Top Control Bar ---
        control_frame = Frame(self)
        control_frame.pack(side="top", fill="x", pady=5, padx=5)
        thumb_size_label = Label(control_frame, text="Thumbnail Size:")
        thumb_size_label.pack(side="left", padx=(0, 2))
        thumb_size_slider = Scale(control_frame, from_=32, to=256, orient=tk.HORIZONTAL, length=150,
                                  variable=self.thumbnail_size, command=self.apply_thumbnail_size)
        thumb_size_slider.pack(side="left", padx=(0, 10))
        load_image_button = Button(control_frame, text="Load Images", command=self.load_images_dialog)
        load_image_button.pack(side="left", padx=5)
        delete_button = Button(control_frame, text="Delete Selected", command=self.delete_selected_files)
        delete_button.pack(side="left", padx=5)

        # --- Scrollable Area ---
        scroll_frame = Frame(self, bd=1, relief="sunken")
        scroll_frame.pack(side="top", fill="both", expand=True, padx=5, pady=(0,5))
        v_scrollbar = Scrollbar(scroll_frame, orient="vertical")
        v_scrollbar.pack(side="right", fill="y")
        self.canvas = Canvas(scroll_frame, bd=0, highlightthickness=0, yscrollcommand=v_scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        v_scrollbar.config(command=self.canvas.yview)
        self.inner_frame = Frame(self.canvas) # Holds the items
        self.inner_frame_id = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw", tags="inner_frame")

        # --- Bindings for Scrolling and Resize ---
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.inner_frame.bind('<Configure>', self._on_inner_frame_configure)
        for widget in [self.canvas, self.inner_frame]:
            widget.bind("<MouseWheel>", self._on_mousewheel, add='+')
            widget.bind("<Button-4>", self._on_mousewheel, add='+')
            widget.bind("<Button-5>", self._on_mousewheel, add='+')
        logging.debug("GridWindow UI setup complete.")

    def _on_canvas_configure(self, event):
        """Adjust width of inner frame to match canvas width."""
        # Set inner frame width based on cols * (thumb_size + padding) or canvas width?
        # Let's keep it simple and match canvas width, grid layout handles columns.
        if self.canvas.winfo_width() != self.inner_frame.winfo_reqwidth():
             self.canvas.itemconfig(self.inner_frame_id, width=event.width)

    def _on_inner_frame_configure(self, event=None):
        """Update canvas scrollregion."""
        bbox = self.canvas.bbox("all");
        if bbox: self.canvas.config(scrollregion=bbox)

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        widget_under_mouse = self.winfo_containing(event.x_root, event.y_root)
        target_canvas = self.canvas; is_over_target = False; check_widget = widget_under_mouse
        while check_widget is not None:
             if check_widget == target_canvas: is_over_target = True; break
             if check_widget == self.winfo_toplevel(): break
             check_widget = check_widget.master
        if not is_over_target: return

        if event.num == 5 or event.delta < 0: scroll_val = 1
        elif event.num == 4 or event.delta > 0: scroll_val = -1
        else: return
        self.canvas.yview_scroll(scroll_val, "units")

    # --- Image Loading and Display ---
    def _load_images_from_config(self):
        initial_paths = self.config.get("images", [])
        logging.info(f"Loading initial images from config: {len(initial_paths)} paths.")
        self.add_images(initial_paths)

    def load_images_dialog(self):
        file_paths = filedialog.askopenfilenames(title="Select Images", filetypes=[("Image Files","*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff"), ("All Files","*.*")])
        if file_paths: logging.info(f"User selected {len(file_paths)} files."); self.add_images(file_paths)

    def add_images(self, file_paths):
        """Adds multiple images, checking for duplicates."""
        added_count = 0; skipped_count = 0; needs_redisplay = False
        for file_path in file_paths:
            if not isinstance(file_path, str) or not file_path: continue
            try:
                norm_path = os.path.normpath(os.path.abspath(file_path))
                if not os.path.isfile(norm_path): logging.warning(f"Skipping non-file: '{file_path}'"); skipped_count += 1; continue
                if norm_path in self.images_data: logging.warning(f"Skipping duplicate: {os.path.basename(norm_path)}"); skipped_count += 1; continue
                pil_img = Image.open(norm_path); pil_img.load()
                self.images_data[norm_path] = {'pil_image': pil_img, 'thumb_photo': None, 'item_frame': None}
                added_count += 1; needs_redisplay = True
                logging.debug(f"Added image data for: {os.path.basename(norm_path)}")
            except FileNotFoundError: logging.warning(f"File not found error for: '{file_path}'") ; skipped_count += 1
            except Exception as e: logging.error(f"Error loading image '{file_path}': {e}", exc_info=True); skipped_count += 1
        if needs_redisplay: self._redisplay_images()
        logging.info(f"Finished adding images. Added: {added_count}, Skipped/Errors: {skipped_count}")

    def _redisplay_images(self):
        """Clears and redraws thumbnails in a FIXED 4-COLUMN grid layout."""
        logging.debug("Redisplaying thumbnails in 4-column grid layout...")
        for widget in self.inner_frame.winfo_children(): widget.destroy()
        self.thumb_tk_images.clear()
        self.sorted_paths = sorted(self.images_data.keys())

        max_thumb_size = self.thumbnail_size.get()
        padding = 5
        # *** USE FIXED NUMBER OF COLUMNS ***
        cols = self.fixed_columns
        row, col = 0, 0
        logging.debug(f"Layout: ThumbSize={max_thumb_size}, Pad={padding}, Cols={cols}")

        for idx, filepath in enumerate(self.sorted_paths):
            data = self.images_data[filepath]
            pil_image = data.get('pil_image')
            item_frame = None
            if pil_image is None: logging.warning(f"PIL Image data missing for {filepath}"); continue

            try:
                thumb_pil = resize_image_keeping_aspect_ratio(pil_image, max_thumb_size, max_thumb_size)
                thumb_photo = ImageTk.PhotoImage(thumb_pil)
                data['thumb_photo'] = thumb_photo; self.thumb_tk_images.append(thumb_photo)

                item_frame = Frame(self.inner_frame, relief="flat", borderwidth=1)
                data['item_frame'] = item_frame; item_frame.filepath = filepath

                img_label = Label(item_frame, image=thumb_photo, borderwidth=0)
                img_label.pack(side="top")
                basename = os.path.basename(filepath); display_name = basename if len(basename) < 25 else basename[:22] + "..."
                name_label_width = max(10, int(max_thumb_size / 6.5))
                name_label = Label(item_frame, text=display_name, font=("Arial", 8), width=name_label_width, anchor='n')
                name_label.pack(side="top", fill="x", pady=(0,2))

                # Bind events
                for widget in [item_frame, img_label, name_label]:
                    widget.bind("<Button-1>", lambda e, p=filepath, i=idx: self._handle_item_click(e, p, i))
                    if sys.platform == "darwin": widget.bind("<Command-Button-1>", lambda e, p=filepath: self._handle_toggle_click(e, p))
                    else: widget.bind("<Control-Button-1>", lambda e, p=filepath: self._handle_toggle_click(e, p))
                    widget.bind("<Shift-Button-1>", lambda e, i=idx: self._handle_shift_click(e, i))
                    widget.bind("<B1-Motion>", lambda e, p=filepath, w=item_frame: self._handle_item_drag(e, p, w))
                    widget.bind("<ButtonRelease-1>", lambda e: self._handle_item_release(e))

                # *** Use grid() layout manager ***
                item_frame.grid(row=row, column=col, padx=padding, pady=padding, sticky="nw")
                self._update_item_visual(item_frame, filepath in self.selected_paths)

                # Move to next grid position (wrapping after fixed columns)
                col += 1
                if col >= cols: col = 0; row += 1

            except Exception as e:
                logging.error(f"Error creating thumbnail widget for {filepath}: {e}", exc_info=True)
                if item_frame and item_frame.winfo_exists(): item_frame.destroy()
                # Display error placeholder
                error_frame = Frame(self.inner_frame, relief="solid", borderwidth=1, bg="red", width=max_thumb_size, height=max_thumb_size+20)
                error_frame.pack_propagate(False)
                Label(error_frame, text="ERR", fg="white", bg="red", font=("Arial", 10, "bold")).pack(pady=5, expand=True)
                basename = os.path.basename(filepath); display_name = basename if len(basename) < 20 else basename[:17] + "..."
                Label(error_frame, text=display_name, font=("Arial", 8), fg="white", bg="red").pack(side="bottom")
                error_frame.grid(row=row, column=col, padx=padding, pady=padding, sticky="nw")
                col += 1
                if col >= cols: col = 0; row += 1

        # Configure columns to have equal weight? Helps with resizing if needed.
        # for i in range(cols):
        #    self.inner_frame.columnconfigure(i, weight=1)

        self.inner_frame.update_idletasks()
        self.canvas.after_idle(self._on_inner_frame_configure)
        logging.debug("Thumbnail redisplay (fixed grid layout) finished.")

    # --- Size, Selection, Deletion ---
    def apply_thumbnail_size(self, value=None):
        logging.debug(f"Thumbnail size changed to: {self.thumbnail_size.get()}")
        self._redisplay_images()

    def _handle_item_click(self, event, filepath, index):
        """Handle plain click (Selects item, deselects others). Sets anchor."""
        logging.debug(f"Item clicked: {os.path.basename(filepath)} at index {index}")
        self.selected_paths.clear(); self.selected_paths.add(filepath)
        self.last_selected_anchor_path = filepath
        self._update_all_item_visuals()
        self.drag_data = {"filepath": filepath, "widget": event.widget, "x": event.x_root, "y": event.y_root, "toplevel": None}

    def _handle_toggle_click(self, event, filepath):
        """Handle Ctrl/Cmd click (Toggles selection). Updates anchor."""
        logging.debug(f"Toggle click: {os.path.basename(filepath)}")
        if filepath in self.selected_paths: self.selected_paths.remove(filepath)
        else: self.selected_paths.add(filepath)
        self.last_selected_anchor_path = filepath
        self._update_all_item_visuals()
        self.drag_data["filepath"] = None # Prevent drag start

    def _handle_shift_click(self, event, clicked_index):
        """Handle Shift click (Selects range)."""
        logging.debug(f"Shift click: index {clicked_index}")
        if self.last_selected_anchor_path is None or self.last_selected_anchor_path not in self.images_data:
            self._handle_item_click(event, self.sorted_paths[clicked_index], clicked_index); return
        try:
            anchor_index = self.sorted_paths.index(self.last_selected_anchor_path)
            start = min(anchor_index, clicked_index); end = max(anchor_index, clicked_index)
            self.selected_paths.clear()
            for i in range(start, end + 1): self.selected_paths.add(self.sorted_paths[i])
            self._update_all_item_visuals()
        except (ValueError, IndexError) as e:
            logging.warning(f"Shift-click error ({e}). Treating as normal click.")
            self._handle_item_click(event, self.sorted_paths[clicked_index], clicked_index)
        self.drag_data["filepath"] = None # Prevent drag start

    def _update_item_visual(self, item_frame, is_selected):
        """Update appearance of one item frame."""
        if item_frame and item_frame.winfo_exists():
           if is_selected: item_frame.config(relief="solid", bg="lightblue")
           else: item_frame.config(relief="flat", bg=self.inner_frame.cget('bg'))

    def _update_all_item_visuals(self):
         """Iterate through displayed items and update visuals."""
         logging.debug(f"Updating all visuals. Selected: {len(self.selected_paths)}")
         for item_frame in self.inner_frame.winfo_children():
             if isinstance(item_frame, Frame) and hasattr(item_frame, 'filepath'):
                 is_selected = item_frame.filepath in self.selected_paths
                 self._update_item_visual(item_frame, is_selected)

    def delete_selected_files(self):
        """Deletes selected items from panel data and redraws."""
        if not self.selected_paths: messagebox.showinfo("Delete", "No images selected."); return
        num = len(self.selected_paths)
        confirm = messagebox.askyesno("Delete", f"Remove {num} selected image(s) from panel?")
        if confirm:
            logging.info(f"Deleting {num} items...")
            for filepath in list(self.selected_paths):
                if filepath in self.images_data: del self.images_data[filepath]
            self.selected_paths.clear(); self.last_selected_anchor_path = None
            self._redisplay_images()

    # --- Drag and Drop ---
    def _handle_item_drag(self, event, filepath, item_frame):
         """Initiate or update drag operation."""
         if self.drag_data["filepath"] == filepath:
            if not self.drag_data["toplevel"]:
                # Create Toplevel only if mouse moved enough
                if abs(event.x_root - self.drag_data["x"]) > 5 or abs(event.y_root - self.drag_data["y"]) > 5:
                    logging.debug(f"Drag Start: Creating Toplevel for {os.path.basename(filepath)}")
                    try:
                        if not self.app or not self.app.root or not self.app.root.winfo_exists(): logging.error("Drag Start failed: Root missing."); return
                        self.drag_data["toplevel"] = tk.Toplevel(self.app.root)
                        self.drag_data["toplevel"].overrideredirect(True); self.drag_data["toplevel"].attributes("-topmost", True)
                        drag_image = self.images_data[filepath].get('thumb_photo')
                        if drag_image: Label(self.drag_data["toplevel"], image=drag_image, relief="solid", bd=1).pack()
                        else: Label(self.drag_data["toplevel"], text="?", relief="solid", bd=1, bg="yellow").pack()
                        self.drag_data["toplevel"].geometry(f"+{event.x_root + 5}+{event.y_root + 5}")
                    except Exception as e:
                        logging.error(f"Error creating drag toplevel: {e}", exc_info=True)
                        if self.drag_data["toplevel"]: self.drag_data["toplevel"].destroy()
                        self.drag_data["toplevel"] = None
            elif self.drag_data["toplevel"]:
                 try: # Update position
                      if self.drag_data["toplevel"].winfo_exists(): self.drag_data["toplevel"].geometry(f"+{event.x_root + 5}+{event.y_root + 5}")
                 except tk.TclError: self.drag_data["toplevel"] = None

    def _handle_item_release(self, event):
        """Handle releasing the dragged item."""
        toplevel_window = self.drag_data.get("toplevel")
        dragged_filepath = self.drag_data.get("filepath")
        self.drag_data = {"filepath": None, "widget": None, "x":0, "y":0, "toplevel":None} # Reset
        if toplevel_window:
             logging.debug("Drag End: Releasing item")
             try:
                 if toplevel_window.winfo_exists(): toplevel_window.destroy()
             except tk.TclError: pass
             if dragged_filepath and self.app.canvas_window:
                 try:
                     if self.app.canvas_window.is_above_canvas(event):
                         logging.info(f"Item '{os.path.basename(dragged_filepath)}' dropped on canvas.")
                         pil_image = self.images_data[dragged_filepath].get('pil_image')
                         if pil_image:
                             canvas_widget = self.app.canvas_window.canvas
                             canvas_x = event.x_root - canvas_widget.winfo_rootx(); canvas_y = event.y_root - canvas_widget.winfo_rooty()
                             self.app.canvas_window.add_image(pil_image, dragged_filepath, canvas_x, canvas_y)
                             if hasattr(self.app, 'add_to_filelist'): self.app.add_to_filelist(dragged_filepath)
                         else: logging.error(f"Cannot drop: PIL image missing for {dragged_filepath}")
                     else: logging.debug("Item released outside main canvas.")
                 except Exception as e: logging.error(f"Error processing drop: {e}", exc_info=True)

    # --- Public Access ---
    def get_image_paths(self):
        """Returns a list of currently loaded image file paths."""
        return self.sorted_paths

    def update_image_in_grid(self, filename, updated_pil_image):
         """Updates PIL data and triggers redisplay."""
         norm_path = os.path.normpath(os.path.abspath(filename))
         if norm_path in self.images_data:
             logging.debug(f"GridWindow updating PIL for: {os.path.basename(norm_path)}")
             self.images_data[norm_path]['pil_image'] = updated_pil_image
             self._redisplay_images() # Simple redisplay
         else: logging.warning(f"GridWindow update requested for unknown file: {filename}")