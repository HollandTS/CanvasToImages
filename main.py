# --- main.py ---
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import json
import logging
from PIL import ImageGrab, Image, ImageTk
import io
import platform
from grid_window import GridWindow
from canvas.view import CanvasWindow
import glob

logging.basicConfig(filename='debug.log', level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s')

class StreamToLogger:
    def __init__(self, logger, log_level=logging.INFO): self.logger=logger; self.log_level=log_level; self.linebuf=''
    def write(self, buf):
        for line in buf.rstrip().splitlines(): self.logger.log(self.log_level, line.rstrip())
    def flush(self): pass

class TerrainToolApp:
    def __init__(self, root):
        try:
            logging.info("Initializing TerrainToolApp")
            self.root = root; self.root.title("Canvas To Images"); self.config_file = "config.json"
            self.selecting_transparency_color = False; self.selected_grid = tk.StringVar()
            self.grid_window = None; self.canvas_window = None
            self.capture_mode_var = tk.StringVar(value="View") # Default capture mode
            self.canvas_width_var = tk.StringVar(value="1500")
            self.canvas_height_var = tk.StringVar(value="1500")
            self.layer_behind_mode = tk.BooleanVar(value=False)
            self.invert_transparency = tk.BooleanVar(value=False)
            self.tolerance_value = tk.IntVar(value=0)
            self.current_palette = None
            self.palette_colors = None
            self.setup_ui()
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.bind("<KeyPress-z>", self.trigger_reset_zoom); self.root.bind("<KeyPress-Z>", self.trigger_reset_zoom)
        except Exception as e: logging.error(f"Error initializing: {e}", exc_info=True)

    # Compatibility for old code expecting selecting_bg_color
    @property
    def selecting_bg_color(self):
        return getattr(self, 'selecting_transparency_color', False)
    @selecting_bg_color.setter
    def selecting_bg_color(self, value):
        self.selecting_transparency_color = value

    def setup_ui(self):
        try:
            logging.info("Setting up UI")
            self.main_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL); self.main_frame.pack(fill="both", expand=True)
            # Left Panel
            self.file_manager_frame = ttk.Frame(self.main_frame); self.main_frame.add(self.file_manager_frame, weight=1)
            self.grid_window = GridWindow(self.file_manager_frame, self.load_config(), self); self.grid_window.pack(fill="both", expand=True)
            # Right Panel
            self.canvas_frame = ttk.Frame(self.main_frame); self.main_frame.add(self.canvas_frame, weight=3)
            # Top Controls Frame
            self.canvas_controls_frame = tk.Frame(self.canvas_frame, height=65)
            # Row 1
            row1_frame = tk.Frame(self.canvas_controls_frame)
            self.transparency_color_button = tk.Button(row1_frame, text="Transparency Color", command=self.start_select_transparency_color); self.transparency_color_button.pack(side="left", padx=5, pady=2)
            self.tolerance_button = tk.Button(row1_frame, text="Tolerance", command=self.open_tolerance_slider); self.tolerance_button.pack(side="left", padx=2, pady=2)
            self.color_button = self.transparency_color_button  # for compatibility
            self.color_preview = tk.Label(row1_frame, text=" ", bg="black", width=2); self.color_preview.pack(side="left", padx=5, pady=2)
            self.color_entry = tk.Entry(row1_frame, width=8); self.color_entry.insert(0, "#000000"); self.color_entry.bind("<Return>", self.update_transparency_color); self.color_entry.pack(side="left", padx=5, pady=2)
            self.invert_transparency_check = tk.Checkbutton(row1_frame, text="Invert transparency", variable=self.invert_transparency, command=self.on_invert_toggle); self.invert_transparency_check.pack(side="left", padx=5, pady=2)
            self.save_button = tk.Button(row1_frame, text="Save", command=self.save_image); self.save_button.pack(side="left", padx=5, pady=2)
            self.copy_button = tk.Button(row1_frame, text="Copy", command=self.copy_canvas); self.copy_button.pack(side="left", padx=5, pady=2)
            # Capture Mode Radio Buttons
            tk.Label(row1_frame, text="Capture:").pack(side="left", padx=(10, 2), pady=2)
            ttk.Radiobutton(row1_frame, text="View", variable=self.capture_mode_var, value="View").pack(side="left")
            ttk.Radiobutton(row1_frame, text="Images Only", variable=self.capture_mode_var, value="Images Only").pack(side="left")
            ttk.Radiobutton(row1_frame, text="Full Canvas", variable=self.capture_mode_var, value="Full Canvas").pack(side="left")
            self.layer_behind_check = tk.Checkbutton(row1_frame, text="Overlay behind images", variable=self.layer_behind_mode, command=self.on_overlay_behind_toggle); self.layer_behind_check.pack(side="left")
            row1_frame.pack(fill="x", side="top")
            # Row 2
            row2_frame = tk.Frame(self.canvas_controls_frame)
            self.paste_button = tk.Button(row2_frame, text="Paste Image", command=self.paste_image); self.paste_button.pack(side="left", padx=5, pady=2)
            self.delete_canvas_item_button = tk.Button(row2_frame, text="Del", command=self.delete_canvas_item); self.delete_canvas_item_button.pack(side="left", padx=5, pady=2)
            # --- Add Background Color Button ---
            self.bg_color_button = tk.Button(row2_frame, text="Background Color", command=self.open_background_color_picker)
            self.bg_color_button.pack(side="left", padx=5, pady=2)
            # --- Add Background Color Pick Button ---
            self.bg_color_pick_button = tk.Button(row2_frame, text="Pick", command=self.start_pick_background_color)
            self.bg_color_pick_button.pack(side="left", padx=2, pady=2)
            # Canvas Size Controls (to the right)
            self.update_size_button = tk.Button(row2_frame, text="Update Size", command=self.update_canvas_size); self.update_size_button.pack(side="right", padx=5, pady=2)
            self.height_entry = tk.Entry(row2_frame, textvariable=self.canvas_height_var, width=6); self.height_entry.pack(side="right", padx=(0, 10), pady=2)
            tk.Label(row2_frame, text="H:").pack(side="right", pady=2)
            self.width_entry = tk.Entry(row2_frame, textvariable=self.canvas_width_var, width=6); self.width_entry.pack(side="right", padx=(0, 5), pady=2)
            tk.Label(row2_frame, text="W:").pack(side="right", pady=2)
            tk.Label(row2_frame, text="Canvas Size:").pack(side="right", padx=(10, 2), pady=2)
            row2_frame.pack(fill="x", side="top")
            self.canvas_controls_frame.pack(fill="x", side="top")
            # --- Add visual separators for control grouping ---
            ttk.Separator(self.canvas_controls_frame, orient='horizontal').pack(fill='x', pady=3)
            # Bottom Controls
            self.bottom_controls_frame = tk.Frame(self.canvas_frame); self.bottom_controls_frame.pack(fill="x", side="bottom", pady=5)
            self.grid_label = tk.Label(self.bottom_controls_frame, text="Grid:"); self.grid_label.pack(side="left", padx=(10, 2))
            self.grid_combobox = ttk.Combobox(self.bottom_controls_frame, textvariable=self.selected_grid, state="readonly", width=15); self.grid_combobox.pack(side="left", padx=(0, 10)); self.grid_combobox.bind("<<ComboboxSelected>>", self.on_grid_selected); self.load_grid_options()
            # --- Add Load Palette Button ---
            self.load_palette_button = tk.Button(self.bottom_controls_frame, text="Load Palette", command=self.on_load_palette)
            self.load_palette_button.pack(side="left", padx=(0, 2))
            self.clear_palette_button = tk.Button(self.bottom_controls_frame, text="X", command=self.on_clear_palette, width=2, fg="red")
            self.clear_palette_button.pack(side="left", padx=(0, 10))
            self.refresh_button = tk.Button(self.bottom_controls_frame, text="Refresh Tool", command=self.refresh_tool); self.refresh_button.pack(side="right", padx=5)
            self.load_layout_button = tk.Button(self.bottom_controls_frame, text="Load Layout", command=self.load_canvas_layout); self.load_layout_button.pack(side="right", padx=5)
            self.save_layout_button = tk.Button(self.bottom_controls_frame, text="Save Layout", command=self.save_canvas_layout); self.save_layout_button.pack(side="right", padx=5)
            self.apply_button = tk.Button(self.bottom_controls_frame, text="Apply Canvas to Images", command=self.apply_canvas_to_images); self.apply_button.pack(side="right", padx=5)
            # Canvas Window
            try: init_w = int(self.canvas_width_var.get()); init_h = int(self.canvas_height_var.get())
            except ValueError: init_w = 1500; init_h = 1500; self.canvas_width_var.set("1500"); self.canvas_height_var.set("1500")
            self.canvas_window = CanvasWindow(self.canvas_frame, self.grid_window, self, initial_width=init_w, initial_height=init_h)
            self.canvas_window.pack(side="top", fill="both", expand=True)
            if not self.grid_combobox['values']: self.grid_combobox['values'] = ["None"]; self.selected_grid.set("None")
        except Exception as e: logging.error(f"Error setting up UI: {e}", exc_info=True)

    # --- Canvas Size Update Command ---
    def update_canvas_size(self):
        try:
            new_w = int(self.canvas_width_var.get()); new_h = int(self.canvas_height_var.get())
            if new_w < 50 or new_h < 50: messagebox.showerror("Invalid Size", "Min size 50x50."); return
            logging.info(f"Updating canvas world size to {new_w}x{new_h}")
            if hasattr(self.canvas_window, 'set_world_size'): self.canvas_window.set_world_size(new_w, new_h)
            else: logging.error("Canvas missing 'set_world_size'!"); messagebox.showerror("Error", "Update fn missing.")
        except ValueError: messagebox.showerror("Invalid Size", "Enter integers.")
        except Exception as e: logging.error(f"Error update canvas size: {e}", exc_info=True); messagebox.showerror("Error", f"Update failed:\n{e}")

    # --- Button Commands ---
    def copy_canvas(self):
        try:
            logging.info(f"Copy Canvas requested (Mode: {self.capture_mode_var.get()})...")
            if not (hasattr(self.canvas_window, 'current_scale_factor') and abs(self.canvas_window.current_scale_factor - 1.0) < 0.001): messagebox.showwarning("Zoom Error", "Please reset zoom to 100% before copying."); logging.warning("Copy cancelled: Zoom not 100%."); return
            if not hasattr(self.canvas_window, 'get_canvas_as_image'): logging.error("Copy Error"); messagebox.showerror("Error", "Copy fn missing."); return
            img = self.canvas_window.get_canvas_as_image(capture_mode=self.capture_mode_var.get()) # Pass mode
            if not img: messagebox.showwarning("Copy", "Could not capture canvas."); return
            output = io.BytesIO(); img.save(output, "BMP"); data = output.getvalue(); output.close()
            try:
                if platform.system() == "Windows":
                    import win32clipboard; import win32con
                    win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.SetClipboardData(win32con.CF_DIB, data[14:]); win32clipboard.CloseClipboard()
                    logging.info("Canvas copied (Win BMP)."); messagebox.showinfo("Copy", "Canvas copied (BMP).")
                else: logging.warning("Direct clipboard copy NYI."); messagebox.showinfo("Copy", "Conceptual Copy OK (OS copy NYI).")
            except ImportError: logging.warning("Lib 'pywin32' missing."); messagebox.showinfo("Copy", "Conceptual Copy OK (Need 'pywin32').")
            except Exception as clip_err: logging.error(f"Clipboard error: {clip_err}", exc_info=True); messagebox.showwarning("Copy", "Could not set clipboard.")
        except Exception as e: logging.error(f"Error in copy_canvas: {e}", exc_info=True); messagebox.showerror("Error", "Copy failed.")

    def delete_canvas_item(self):
        try:
            logging.info("Requesting canvas item deletion.")
            if hasattr(self.canvas_window, 'delete_selection_or_last_clicked'): self.canvas_window.delete_selection_or_last_clicked()
            else: logging.error("Canvas missing delete method!"); messagebox.showerror("Error", "Delete fn missing.")
        except Exception as e: logging.error(f"Error delete canvas item: {e}", exc_info=True); messagebox.showerror("Error", "Delete failed.")

    def save_canvas_layout(self):
        logging.info("Saving canvas layout...")
        if not hasattr(self.canvas_window, 'get_layout_data'): logging.error("Save Layout Error"); messagebox.showerror("Error","Save fn missing."); return
        layout_data = self.canvas_window.get_layout_data()
        if not layout_data: messagebox.showwarning("Save Layout", "No layout data."); return
        # Add current capture mode to saved data
        layout_data["settings"]["capture_mode"] = self.capture_mode_var.get()
        file_path = filedialog.asksaveasfilename(title="Save Canvas Layout", defaultextension=".json", filetypes=[("Canvas Layout","*.json"),("All","*.*")])
        if not file_path: logging.info("Save cancelled."); return
        try:
            with open(file_path, 'w') as f: json.dump(layout_data, f, indent=4)
            logging.info(f"Layout saved: {file_path}"); messagebox.showinfo("Save Layout", f"Saved:\n{os.path.basename(file_path)}")
        except Exception as e: logging.error(f"Error saving layout file {file_path}: {e}", exc_info=True); messagebox.showerror("Save Error", f"Could not write file:\n{e}")

    def load_canvas_layout(self):
        logging.info("Loading canvas layout...")
        file_path = filedialog.askopenfilename(title="Load Canvas Layout", filetypes=[("Canvas Layout","*.json"),("All","*.*")])
        if not file_path: logging.info("Load cancelled."); return
        try:
            with open(file_path, 'r') as f: layout_data = json.load(f)
            logging.info(f"Loaded layout data from {file_path}")
            if not isinstance(layout_data, dict) or "canvas_items" not in layout_data: raise ValueError("Invalid format.")
            items_to_place = []; missing_files = []; loaded_grid_images = self.grid_window.images_data
            for item_data in layout_data.get("canvas_items", []):
                fp = item_data.get('filepath'); x = item_data.get('x'); y = item_data.get('y')
                if fp and isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    if fp in loaded_grid_images:
                        pil_image = loaded_grid_images[fp].get('pil_image')
                        if pil_image: items_to_place.append({'pil_image': pil_image, 'filepath': fp, 'x': x, 'y': y})
                        else: missing_files.append(os.path.basename(fp))
                    else: missing_files.append(os.path.basename(fp))
                else: logging.warning(f"Skipping invalid item data: {item_data}")
            settings_data = layout_data.get("settings", {}); overlay_data = layout_data.get("overlay", {})
            capture_origin = settings_data.get("capture_origin")
            # Load and set capture mode radio button
            loaded_capture_mode = settings_data.get("capture_mode", "View")
            if loaded_capture_mode not in ["View", "Images Only", "Full Canvas"]: loaded_capture_mode = "View"
            self.capture_mode_var.set(loaded_capture_mode)
            self.canvas_width_var.set(str(settings_data.get("canvas_width", 1500)))
            self.canvas_height_var.set(str(settings_data.get("canvas_height", 1500)))
            if hasattr(self.canvas_window, 'apply_layout'):
                self.canvas_window.apply_layout(items_to_place, settings_data, overlay_data, capture_origin)
                logging.info("Layout applied.")
                msg = "Layout loaded."
                if missing_files: msg += "\n\nWarn: Images not in panel:\n" + "\n".join(missing_files)
                if overlay_data: msg += "\n\nPaste overlay to restore."
                messagebox.showinfo("Load Layout", msg)
            else: logging.error("Canvas missing 'apply_layout'!"); messagebox.showerror("Load Error", "Load fn missing.")
        except FileNotFoundError: logging.error(f"Layout file not found: {file_path}"); messagebox.showerror("Load Error", f"File not found:\n{file_path}")
        except json.JSONDecodeError as e: logging.error(f"JSON decode error {file_path}: {e}"); messagebox.showerror("Load Error", f"Invalid JSON format:\n{file_path}\n{e}")
        except ValueError as e: logging.error(f"Invalid layout data {file_path}: {e}"); messagebox.showerror("Load Error", f"Invalid data:\n{file_path}\n{e}")
        except Exception as e: logging.error(f"Error loading layout {file_path}: {e}", exc_info=True); messagebox.showerror("Load Error", f"Unexpected error:\n{e}")

    # --- Grid Handling Methods ---
    def load_grid_options(self):
        # *** Corrected try-except block ***
        try:
            grid_dir="grids"; options=["None"];
            if os.path.isdir(grid_dir):
                options.extend(sorted([os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(grid_dir,"*.grid"))]))
            else:
                logging.warning(f"Grids dir '{grid_dir}' not found.")
            self.grid_combobox['values']=options
            logging.info(f"Grids: {options}")
            if self.selected_grid.get() not in options: self.selected_grid.set("None")
        except Exception as e:
            logging.error(f"Grid load error: {e}",exc_info=True)
            self.grid_combobox['values'] = ["None"]
            self.selected_grid.set("None")
            
    def on_grid_selected(self, event=None):
        name=self.selected_grid.get(); logging.info(f"Grid selected: {name}"); info=None
        if name != "None":
            parts=name.lower().split(); type=None; params={}
            if "px" in name: type="pixel";
            elif parts[0]=="diamond" or "w" in name or "h" in name: type="diamond";
            if type=="pixel":
                for p in parts:
                    if p.endswith("px"):
                        try: params["step"]=int(p[:-2]); break
                        except: pass
                if not params.get("step") or params["step"]<=0: type=None
            elif type=="diamond":
                w=None; h=None;
                for p in parts:
                    if p.endswith("w"):
                        try: w=int(p[:-1])
                        except: pass
                    elif p.endswith("h"):
                        try: h=int(p[:-1])
                        except: pass
                if w and w>0 and h and h>0: params["cell_width"]=w; params["cell_height"]=h
                else: type=None
            if type: info={"type":type, "name":name, **params}
            else: logging.warning(f"Bad grid name: {name}"); messagebox.showwarning("Grid Error",f"Invalid name '{name}'."); self.selected_grid.set("None")
        if hasattr(self.canvas_window,'update_grid'): self.canvas_window.update_grid(info)
        else: logging.error("Canvas missing 'update_grid'!")

    # --- Palette Handling Methods ---
    def on_clear_palette(self):
        self.current_palette = None
        self.palette_colors = None
        # Refresh all tiles to original images
        if hasattr(self.canvas_window, 'refresh_all_tiles_to_original'):
            self.canvas_window.refresh_all_tiles_to_original()
        messagebox.showinfo("Palette Cleared", "Palette has been removed. Images will use their original colors.")
        # Optionally, reload original images if you have them cached

    def on_load_palette(self):
        file_path = filedialog.askopenfilename(title="Select Palette Image", filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("All Files", "*.*")])
        if not file_path:
            return
        try:
            palette_img = Image.open(file_path).convert("RGB")
            palette_colors = self.extract_palette_colors(palette_img)
            if not palette_colors:
                messagebox.showerror("Palette Error", "No colors found in palette image.")
                return
            self.current_palette = file_path
            self.palette_colors = palette_colors
            self.apply_palette_to_canvas_images(palette_colors)
            messagebox.showinfo("Palette Applied", f"Applied palette with {len(palette_colors)} colors.")
        except Exception as e:
            logging.error(f"Error loading palette: {e}", exc_info=True)
            messagebox.showerror("Palette Error", f"Failed to load palette: {e}")

    def extract_palette_colors(self, palette_img, max_colors=256):
        # Reduce to unique colors, up to max_colors
        colors = palette_img.getcolors(maxcolors=palette_img.width * palette_img.height)
        if not colors:
            # fallback: quantize
            palette_img = palette_img.convert('P', palette=Image.ADAPTIVE, colors=max_colors)
            palette = palette_img.getpalette()[:max_colors*3]
            return [tuple(palette[i:i+3]) for i in range(0, len(palette), 3)]
        # sort by count, take up to max_colors
        colors = sorted(colors, reverse=True)
        return [c[1] for c in colors[:max_colors]]

    def apply_palette_to_canvas_images(self, palette_colors):
        # Remap all images on the canvas to use only the palette colors
        if not hasattr(self.canvas_window, 'remap_all_images_to_palette'):
            messagebox.showerror("Not Supported", "Canvas does not support palette remapping.")
            return
        self.canvas_window.remap_all_images_to_palette(palette_colors)

    # --- Other Methods ---
    def delete_selected_files(self): # Left panel delete
        try:
            if hasattr(self.grid_window, 'delete_selected_files'): self.grid_window.delete_selected_files()
        except Exception as e: logging.error(f"Error deleting grid items: {e}", exc_info=True)
    def start_select_transparency_color(self):
        try: self.selecting_transparency_color = True; self.root.config(cursor="cross")
        except Exception as e: logging.error(f"Error start transparency color select: {e}", exc_info=True)
    def select_transparency_color(self, color):
        try:
            self.color_preview.config(bg=color); self.color_entry.delete(0, tk.END); self.color_entry.insert(0, color)
            if hasattr(self.canvas_window, 'set_transparency_color'):
                self.canvas_window.set_transparency_color(color)
            self.selecting_transparency_color = False; self.root.config(cursor="")
        except Exception as e: logging.error(f"Error selecting transparency color: {e}", exc_info=True)
    def cancel_select_transparency_color(self):
         self.selecting_transparency_color = False; self.root.config(cursor=""); logging.debug("Transparency color select cancelled.")
    def update_transparency_color(self, event):
        try: color = self.color_entry.get(); self.select_transparency_color(color)
        except Exception as e: logging.error(f"Error update transparency color entry: {e}", exc_info=True)
    def start_select_background_color(self):
        self.start_select_transparency_color()
    def select_background_color(self, color):
        self.select_transparency_color(color)
    def cancel_select_background_color(self):
        self.cancel_select_transparency_color()
    def update_background_color(self, event):
        self.update_transparency_color(event)
    def save_image(self):
        try:
            f_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
            if f_path and hasattr(self.canvas_window, 'save_canvas_image'):
                 # Pass capture mode from radio buttons
                 self.canvas_window.save_canvas_image(f_path, capture_mode=self.capture_mode_var.get())
        except Exception as e: logging.error(f"Error saving image: {e}", exc_info=True)
    def paste_image(self):
        try:
            if hasattr(self.canvas_window, 'paste_image_from_clipboard'): self.canvas_window.paste_image_from_clipboard()
        except Exception as e: logging.error(f"Error pasting image: {e}", exc_info=True)
    def apply_canvas_to_images(self):
        try:
            # Apply function now checks zoom itself
            if hasattr(self, 'palette_colors') and self.palette_colors:
                self.apply_palette_to_canvas_images(self.palette_colors)
            if hasattr(self.canvas_window, 'apply_canvas_to_images'): self.canvas_window.apply_canvas_to_images()
            else: logging.error("Canvas missing apply_canvas_to_images!"); messagebox.showerror("Error", "Apply fn missing.")
        except Exception as e: logging.error(f"Error applying canvas: {e}", exc_info=True)
    def refresh_tool(self):
        try:
            logging.info("Refreshing tool"); self.save_config()
            self.root.destroy(); python = sys.executable; os.execl(python, python, *sys.argv)
        except Exception as e: logging.error(f"Error refreshing: {e}", exc_info=True)
    def save_config(self):
        try:
            if self.grid_window and hasattr(self.grid_window, 'get_image_paths'):
                config = {"images": self.grid_window.get_image_paths()}
                with open(self.config_file, "w") as f: json.dump(config, f, indent=4)
                logging.info(f"Config saved with {len(config['images'])} paths.")
            else: logging.error("Cannot save config: grid_window missing.")
        except Exception as e: logging.error(f"Error saving config: {e}", exc_info=True)
    def load_config(self):
        try:
            logging.info(f"Loading config from {self.config_file}")
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f: config_data = json.load(f)
                if isinstance(config_data,dict) and isinstance(config_data.get("images"),list): return config_data
            return {}
        except json.JSONDecodeError as jde: logging.error(f"Error decoding config '{self.config_file}': {jde}"); return {}
        except Exception as e: logging.error(f"Error loading config: {e}", exc_info=True); return {}
    def on_closing(self):
        logging.info("WM_DELETE_WINDOW event.")
        self.save_config()
        self.root.destroy()
    def trigger_reset_zoom(self, event=None):
        logging.debug("Reset Zoom triggered (Hotkey Z)")
        try:
             if self.canvas_window and hasattr(self.canvas_window, 'reset_zoom'): self.canvas_window.reset_zoom(event)
        except Exception as e: logging.error(f"Error triggering zoom reset: {e}", exc_info=True)
    def on_invert_toggle(self):
        try:
            logging.info("Invert transparency toggled.")
            if hasattr(self.canvas_window, 'redraw_canvas'): self.canvas_window.redraw_canvas()
        except Exception as e: logging.error(f"Error in invert toggle: {e}", exc_info=True)
    def on_overlay_behind_toggle(self):
        try:
            logging.info("Overlay behind images toggled.")
            if hasattr(self.canvas_window, 'update_overlay_stacking'):
                self.canvas_window.update_overlay_stacking()
        except Exception as e:
            logging.error(f"Error in overlay behind toggle: {e}", exc_info=True)

    def open_tolerance_slider(self):
        win = tk.Toplevel(self.root)
        win.title("Transparency Tolerance")
        tk.Label(win, text="Tolerance (0 = exact match)").pack(padx=10, pady=5)
        slider = tk.Scale(win, from_=0, to=64, orient=tk.HORIZONTAL, variable=self.tolerance_value)
        slider.pack(padx=10, pady=5)
        def on_slide(val):
            # Redraw all tiles with new tolerance
            if hasattr(self.canvas_window, 'redraw_canvas'):
                self.canvas_window.redraw_canvas()
        slider.config(command=on_slide)
        def close():
            win.destroy()
        tk.Button(win, text="OK", command=close).pack(pady=5)

    def open_background_color_picker(self):
        try:
            from tkinter import colorchooser
            color_code = colorchooser.askcolor(title="Choose Background Color")
            if color_code and color_code[1]:
                # Set the canvas background color directly, do not touch transparency color
                if hasattr(self.canvas_window, 'set_canvas_background_color'):
                    self.canvas_window.set_canvas_background_color(color_code[1])
        except Exception as e:
            logging.error(f"Error opening background color picker: {e}", exc_info=True)

    def start_pick_background_color(self):
        """Enable pick mode for background color selection from canvas."""
        if hasattr(self.canvas_window, 'enable_background_color_pick_mode'):
            self.canvas_window.enable_background_color_pick_mode()

if __name__ == "__main__":
    logging.info("="*20 + " Starting CanvasToImages " + "="*20)
    try:
        root = tk.Tk(); app = TerrainToolApp(root); root.mainloop()
    except Exception as e:
        logging.error(f"CRITICAL ERROR IN MAIN: {e}", exc_info=True)
        if sys.platform.startswith('win'): input("Press Enter to exit...")
    finally: logging.info("="*20 + " CanvasToImages Exited " + "="*20 + "\n")