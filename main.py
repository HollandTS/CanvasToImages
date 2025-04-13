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
from grid_window import GridWindow # Assuming grid_window.py is stable
from canvas.view import CanvasWindow # Import the view
import glob

# Configure logging
logging.basicConfig(filename='debug.log', level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s')

# Redirect stdout/stderr (optional)
class StreamToLogger:
    def __init__(self, logger, log_level=logging.INFO): self.logger=logger; self.log_level=log_level; self.linebuf=''
    def write(self, buf):
        for line in buf.rstrip().splitlines(): self.logger.log(self.log_level, line.rstrip())
    def flush(self): pass
# sys.stdout = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
# sys.stderr = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)

class TerrainToolApp:
    def __init__(self, root):
        try:
            logging.info("Initializing TerrainToolApp")
            self.root = root; self.root.title("Terrain Tool"); self.config_file = "config.json"
            self.selecting_bg_color = False; self.selected_grid = tk.StringVar()
            self.grid_window = None; self.canvas_window = None
            self.capture_full_layout = tk.BooleanVar(value=False)
            self.setup_ui()
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            # Bind Keypress 'Z' to root window for resetting zoom
            self.root.bind("<KeyPress-z>", self.trigger_reset_zoom)
            self.root.bind("<KeyPress-Z>", self.trigger_reset_zoom)
        except Exception as e: logging.error(f"Error initializing: {e}", exc_info=True)

    def setup_ui(self):
        try:
            logging.info("Setting up UI")
            self.main_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL); self.main_frame.pack(fill="both", expand=True)
            # Left Panel
            self.file_manager_frame = ttk.Frame(self.main_frame); self.main_frame.add(self.file_manager_frame, weight=1)
            self.grid_window = GridWindow(self.file_manager_frame, self.load_config(), self); self.grid_window.pack(fill="both", expand=True)
            # Right Panel
            self.canvas_frame = ttk.Frame(self.main_frame); self.main_frame.add(self.canvas_frame, weight=3)
            # Top Controls
            self.canvas_controls_frame = tk.Frame(self.canvas_frame, height=50)
            self.color_button = tk.Button(self.canvas_controls_frame, text="Select BG Color", command=self.start_select_background_color); self.color_button.pack(side="left", padx=5, pady=5)
            self.color_preview = tk.Label(self.canvas_controls_frame, text=" ", bg="black", width=2); self.color_preview.pack(side="left", padx=5, pady=5)
            self.color_entry = tk.Entry(self.canvas_controls_frame, width=8); self.color_entry.insert(0, "#000000"); self.color_entry.bind("<Return>", self.update_background_color); self.color_entry.pack(side="left", padx=5, pady=5)
            self.save_button = tk.Button(self.canvas_controls_frame, text="Save", command=self.save_image); self.save_button.pack(side="left", padx=5, pady=5)
            self.copy_button = tk.Button(self.canvas_controls_frame, text="Copy", command=self.copy_canvas); self.copy_button.pack(side="left", padx=5, pady=5)
            self.capture_mode_check = tk.Checkbutton(self.canvas_controls_frame, text="Full Layout", variable=self.capture_full_layout, command=lambda: logging.info(f"Capture mode Full Layout: {self.capture_full_layout.get()}")); self.capture_mode_check.pack(side="left", padx=(10, 5), pady=5)
            self.paste_button = tk.Button(self.canvas_controls_frame, text="Paste Image", command=self.paste_image); self.paste_button.pack(side="left", padx=5, pady=5)
            self.delete_canvas_item_button = tk.Button(self.canvas_controls_frame, text="Del", command=self.delete_canvas_item); self.delete_canvas_item_button.pack(side="left", padx=5, pady=5)
            # *** REMOVED Center View Button ***
            # self.center_view_button = tk.Button(...)
            # self.center_view_button.pack(...)
            # ********************************
            self.canvas_controls_frame.pack(fill="x", side="top")
            # Bottom Controls
            self.bottom_controls_frame = tk.Frame(self.canvas_frame); self.bottom_controls_frame.pack(fill="x", side="bottom", pady=5)
            self.grid_label = tk.Label(self.bottom_controls_frame, text="Grid:"); self.grid_label.pack(side="left", padx=(10, 2))
            self.grid_combobox = ttk.Combobox(self.bottom_controls_frame, textvariable=self.selected_grid, state="readonly", width=15); self.grid_combobox.pack(side="left", padx=(0, 10)); self.grid_combobox.bind("<<ComboboxSelected>>", self.on_grid_selected); self.load_grid_options()
            self.refresh_button = tk.Button(self.bottom_controls_frame, text="Refresh Tool", command=self.refresh_tool); self.refresh_button.pack(side="right", padx=5)
            self.load_layout_button = tk.Button(self.bottom_controls_frame, text="Load Layout", command=self.load_canvas_layout); self.load_layout_button.pack(side="right", padx=5)
            self.save_layout_button = tk.Button(self.bottom_controls_frame, text="Save Layout", command=self.save_canvas_layout); self.save_layout_button.pack(side="right", padx=5)
            self.apply_button = tk.Button(self.bottom_controls_frame, text="Apply Canvas to Images", command=self.apply_canvas_to_images); self.apply_button.pack(side="right", padx=5)
            # Canvas Window
            self.canvas_window = CanvasWindow(self.canvas_frame, self.grid_window, self); self.canvas_window.pack(side="top", fill="both", expand=True)
            if not self.grid_combobox['values']: self.grid_combobox['values'] = ["None"]; self.selected_grid.set("None")
        except Exception as e: logging.error(f"Error setting up UI: {e}", exc_info=True)

    # --- Button Commands ---
    def copy_canvas(self):
        try:
            logging.info(f"Copy Canvas requested (Full: {self.capture_full_layout.get()})...")
            if not (hasattr(self.canvas_window, 'current_scale_factor') and abs(self.canvas_window.current_scale_factor - 1.0) < 0.001): messagebox.showwarning("Zoom Error", "Please reset zoom to 100% before copying (Press 'Z')."); logging.warning("Copy cancelled: Zoom not 100%."); return
            if not hasattr(self.canvas_window, 'get_canvas_as_image'): logging.error("Copy Error"); messagebox.showerror("Error", "Copy fn missing."); return
            img = self.canvas_window.get_canvas_as_image(capture_full=self.capture_full_layout.get())
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

    # *** REMOVED Center View Trigger Method ***
    # def trigger_center_view(self): ...
    # *****************************************

    def save_canvas_layout(self):
        logging.info("Saving canvas layout...")
        if not hasattr(self.canvas_window, 'get_layout_data'): logging.error("Save Layout Error"); messagebox.showerror("Error","Save fn missing."); return
        layout_data = self.canvas_window.get_layout_data()
        if not layout_data: messagebox.showwarning("Save Layout", "No layout data."); return
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
            self.capture_full_layout.set(settings_data.get("capture_full_layout", False))
            if hasattr(self.canvas_window, 'apply_layout'):
                self.canvas_window.apply_layout(items_to_place, settings_data, overlay_data, capture_origin)
                logging.info("Layout applied.")
                msg = "Layout loaded."
                if missing_files: msg += "\n\nWarning: Images not in panel:\n" + "\n".join(missing_files)
                if overlay_data: msg += "\n\nPaste overlay to restore."
                messagebox.showinfo("Load Layout", msg)
            else: logging.error("Canvas missing 'apply_layout'!"); messagebox.showerror("Load Error", "Load fn missing.")
        except FileNotFoundError: logging.error(f"Layout file not found: {file_path}"); messagebox.showerror("Load Error", f"File not found:\n{file_path}")
        except json.JSONDecodeError as e: logging.error(f"JSON decode error {file_path}: {e}"); messagebox.showerror("Load Error", f"Invalid JSON format:\n{file_path}\n{e}")
        except ValueError as e: logging.error(f"Invalid layout data {file_path}: {e}"); messagebox.showerror("Load Error", f"Invalid data:\n{file_path}\n{e}")
        except Exception as e: logging.error(f"Error loading layout {file_path}: {e}", exc_info=True); messagebox.showerror("Load Error", f"Unexpected error:\n{e}")

    # --- Grid Handling Methods ---
    def load_grid_options(self):
        try:
            grid_dir="grids"; options=["None"];
            if os.path.isdir(grid_dir): options.extend(sorted([os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(grid_dir,"*.grid"))]))
            else: logging.warning(f"Grids dir '{grid_dir}' not found.")
            self.grid_combobox['values']=options; logging.info(f"Grids: {options}")
            if self.selected_grid.get() not in options: self.selected_grid.set("None")
        except Exception as e: logging.error(f"Grid load error: {e}",exc_info=True); self.grid_combobox['values'] = ["None"]; self.selected_grid.set("None")
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

    # --- Other Methods ---
    def delete_selected_files(self): # Left panel delete
        try:
            if hasattr(self.grid_window, 'delete_selected_files'): self.grid_window.delete_selected_files()
        except Exception as e: logging.error(f"Error deleting grid items: {e}", exc_info=True)
    def start_select_background_color(self):
        try: self.selecting_bg_color = True; self.root.config(cursor="cross")
        except Exception as e: logging.error(f"Error start BG select: {e}", exc_info=True)
    def select_background_color(self, color):
        try:
            self.color_preview.config(bg=color); self.color_entry.delete(0, tk.END); self.color_entry.insert(0, color)
            if hasattr(self.canvas_window, 'set_background_color'): self.canvas_window.set_background_color(color)
            self.selecting_bg_color = False; self.root.config(cursor="")
        except Exception as e: logging.error(f"Error selecting BG: {e}", exc_info=True)
    def cancel_select_background_color(self):
         self.selecting_bg_color = False; self.root.config(cursor=""); logging.debug("BG select cancelled.")
    def update_background_color(self, event):
        try: color = self.color_entry.get(); self.select_background_color(color)
        except Exception as e: logging.error(f"Error update BG entry: {e}", exc_info=True)
    def save_image(self):
        try:
            f_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
            if f_path and hasattr(self.canvas_window, 'save_canvas_image'):
                 self.canvas_window.save_canvas_image(f_path, capture_full=self.capture_full_layout.get())
        except Exception as e: logging.error(f"Error saving image: {e}", exc_info=True)
    def paste_image(self):
        try:
            if hasattr(self.canvas_window, 'paste_image_from_clipboard'): self.canvas_window.paste_image_from_clipboard()
        except Exception as e: logging.error(f"Error pasting image: {e}", exc_info=True)
    def apply_canvas_to_images(self):
        try:
            # Apply function now checks zoom itself
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
                else: logging.warning("Config invalid structure."); return {}
            else: logging.info("Config file not found."); return {}
        except json.JSONDecodeError as jde: logging.error(f"Error decoding config '{self.config_file}': {jde}"); return {}
        except Exception as e: logging.error(f"Error loading config: {e}", exc_info=True); return {}
    def on_closing(self):
        logging.info("WM_DELETE_WINDOW event.")
        self.save_config()
        self.root.destroy()
    def add_to_filelist(self, filename): pass
    def remove_from_filelist(self, filename): pass
    def on_file_listbox_select(self, event): pass

    # *** Added trigger for Zoom Reset hotkey ***
    def trigger_reset_zoom(self, event=None):
        """Tells the canvas window to reset zoom."""
        logging.debug("Reset Zoom triggered (Hotkey Z)")
        try:
             if self.canvas_window and hasattr(self.canvas_window, 'reset_zoom'):
                 # Pass the event if it exists (for showing percentage label)
                 self.canvas_window.reset_zoom(event)
             else: logging.error("CanvasWindow missing or no 'reset_zoom' method!")
        except Exception as e:
            logging.error(f"Error triggering zoom reset: {e}", exc_info=True)

if __name__ == "__main__":
    logging.info("="*20 + " Starting TerrainToolApp " + "="*20)
    try:
        root = tk.Tk(); app = TerrainToolApp(root); root.mainloop()
    except Exception as e:
        logging.error(f"CRITICAL ERROR IN MAIN: {e}", exc_info=True)
        if sys.platform.startswith('win'): input("Press Enter to exit...")
    finally: logging.info("="*20 + " TerrainToolApp Exited " + "="*20 + "\n")