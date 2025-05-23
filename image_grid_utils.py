from PIL import Image, ImageTk
import os
import logging
import tkinter as tk

def load_images_from_config(grid_window):
    try:
        logging.debug("Loading images from config")
        for file_path in grid_window.image_paths:
            if os.path.exists(file_path):
                image = Image.open(file_path)
                grid_window.images.append(image)
        display_images(grid_window)
    except Exception as e:
        logging.error(f"Error loading images from config: {e}")

def display_images(grid_window):
    try:
        logging.debug("Displaying images")
        grid_window.canvas.delete("all")
        grid_window.tk_images = []  # Reset the list of references
        grid_window.image_positions = []  # Reset the list of positions
        grid_window.selection_boxes = {}  # Reset the selection boxes
        for i, image in enumerate(grid_window.images):
            resized_image = resize_image_keeping_aspect_ratio(image, grid_window.grid_size, grid_window.grid_size)
            tk_image = ImageTk.PhotoImage(resized_image)
            grid_window.tk_images.append(tk_image)  # Store reference to prevent garbage collection
            x = (i % grid_window.grid_width) * grid_window.grid_size
            y = (i // grid_window.grid_width) * grid_window.grid_size
            grid_window.image_positions.append((x, y))
            grid_window.canvas.create_image(x, y, anchor="nw", image=tk_image, tags=(str(i), "draggable", "image"))
            grid_window.canvas.create_text(x + grid_window.grid_size // 2, y + grid_window.grid_size + 10, text=os.path.basename(grid_window.image_paths[i]), anchor="n", tags=(str(i), "text"))
        update_selection(grid_window)

        # --- Add mouse bindings for selection, drag, and box select ---
        grid_window.canvas.bind('<ButtonPress-1>', lambda event: handle_image_mouse_down(grid_window, event))
        grid_window.canvas.bind('<B1-Motion>', lambda event: handle_image_mouse_move(grid_window, event))
        grid_window.canvas.bind('<ButtonRelease-1>', lambda event: handle_image_mouse_up(grid_window, event))
        grid_window.canvas.bind('<ButtonPress-3>', lambda event: start_box_select(grid_window, event))
        grid_window.canvas.bind('<B3-Motion>', lambda event: on_box_select(grid_window, event))
        grid_window.canvas.bind('<ButtonRelease-3>', lambda event: end_box_select(grid_window, event))
        grid_window.canvas.bind('<Control-Button-1>', lambda event: handle_ctrl_click(grid_window, event))
        grid_window.canvas.bind('<Shift-Button-1>', lambda event: handle_shift_click(grid_window, event))
    except Exception as e:
        logging.error(f"Error displaying images: {e}")

def resize_image_keeping_aspect_ratio(image, max_width, max_height):
    try:
        width_ratio = max_width / image.width
        height_ratio = max_height / image.height
        resize_ratio = min(width_ratio, height_ratio)
        new_width = int(image.width * resize_ratio)
        new_height = int(image.height * resize_ratio)
        return image.resize((new_width, new_height), Image.LANCZOS)
    except Exception as e:
        logging.error(f"Error resizing image: {e}")
        return image

def update_image_in_grid(grid_window, filename, updated_image):
    try:
        logging.info(f"Updating image in grid: {filename}")
        for idx, image_path in enumerate(grid_window.image_paths):
            if image_path == filename:
                updated_image.thumbnail((grid_window.grid_size, grid_window.grid_size), Image.LANCZOS)
                tk_image = ImageTk.PhotoImage(updated_image)
                grid_window.tk_images[idx] = tk_image
                x = (idx % grid_window.grid_width) * grid_window.grid_size
                y = (idx // grid_window.grid_width) * grid_window.grid_size
                grid_window.canvas.create_image(x, y, anchor="nw", image=tk_image, tags=(str(idx), "draggable", "image"))
                grid_window.canvas.create_text(x + grid_window.grid_size // 2, y + grid_window.grid_size + 10, text=os.path.basename(filename), anchor="n", tags=(str(idx), "text"))
                logging.info(f"Image {filename} updated in grid at ({x}, {y})")
                break
    except Exception as e:
        logging.error(f"Error updating image in grid: {e}")

def handle_image_click(grid_window, event):
    try:
        logging.debug("Image clicked in GridWindow")
        item = grid_window.canvas.find_closest(event.x, event.y)
        if item:
            tags = grid_window.canvas.gettags(item)
            if "image" in tags:
                image_index = int(tags[0])
                # Only change selection if the clicked image is not already selected
                if image_index not in grid_window.selected_items or not grid_window.selected_items:
                    grid_window.selected_items = [image_index]
                    update_selection(grid_window)
                # else: keep current selection (for multi-drag)

            # Prepare for dragging: drag all selected images
            grid_window.drag_data["items"] = [grid_window.canvas.find_withtag(str(i))[0] for i in grid_window.selected_items]
            grid_window.drag_data["x"] = event.x
            grid_window.drag_data["y"] = event.y
            grid_window.drag_data["image_indices"] = list(grid_window.selected_items)

            # Create a floating window for each selected image
            grid_window.drag_data["floating_images"] = []
            for image_index in grid_window.drag_data["image_indices"]:
                image = grid_window.tk_images[image_index]
                floating_image = tk.Toplevel(grid_window)
                floating_image.overrideredirect(True)
                floating_image.geometry(f"+{event.x_root}+{event.y_root}")
                label = tk.Label(floating_image, image=image)
                label.pack()
                grid_window.drag_data["floating_images"].append(floating_image)
            logging.debug(f"Drag data: {grid_window.drag_data}")
    except Exception as e:
        logging.error(f"Error handling image click in GridWindow: {e}")

def handle_image_drag(grid_window, event):
    try:
        for floating_image in grid_window.drag_data["floating_images"]:
            floating_image.geometry(f"+{event.x_root}+{event.y_root}")
    except Exception as e:
        logging.error(f"Error handling image drag in GridWindow: {e}")

def handle_image_release(grid_window, event):
    try:
        for floating_image in grid_window.drag_data["floating_images"]:
            floating_image.destroy()
        # Debug: log the indices being dropped
        logging.debug(f"handle_image_release: image_indices = {grid_window.drag_data['image_indices']}")
        if grid_window.app.canvas_window.is_above_canvas(event):
            indices = grid_window.drag_data["image_indices"]
            n = len(indices)
            if n == 0:
                return
            import math
            grid_cols = math.ceil(math.sqrt(n))
            grid_rows = math.ceil(n / grid_cols)
            spacing = 32  # You can adjust this spacing as needed
            x0 = event.x_root - grid_window.app.canvas_window.canvas.winfo_rootx()
            y0 = event.y_root - grid_window.app.canvas_window.canvas.winfo_rooty()
            for idx, image_index in enumerate(indices):
                image = grid_window.images[image_index]
                filename = grid_window.image_paths[image_index]
                row = idx // grid_cols
                col = idx % grid_cols
                x = x0 + col * spacing
                y = y0 + row * spacing
                grid_window.app.canvas_window.add_image(image, filename, x, y)
                grid_window.app.add_to_filelist(filename)
        grid_window.drag_data = {"x": 0, "y": 0, "items": [], "image_indices": [], "floating_images": []}
    except Exception as e:
        logging.error(f"Error handling image release in GridWindow: {e}")

def handle_ctrl_click(grid_window, event):
    try:
        logging.debug("Ctrl-click in GridWindow")
        item = grid_window.canvas.find_closest(event.x, event.y)
        if item:
            tags = grid_window.canvas.gettags(item)
            if "image" in tags:
                image_index = int(tags[0])
                if image_index in grid_window.selected_items:
                    grid_window.selected_items.remove(image_index)
                else:
                    grid_window.selected_items.append(image_index)
                update_selection(grid_window)
    except Exception as e:
        logging.error(f"Error handling ctrl-click in GridWindow: {e}")

def handle_shift_click(grid_window, event):
    try:
        logging.debug("Shift-click in GridWindow")
        item = grid_window.canvas.find_closest(event.x, event.y)
        if item:
            tags = grid_window.canvas.gettags(item)
            if "image" in tags:
                image_index = int(tags[0])
                if grid_window.selected_items:
                    start_index = min(grid_window.selected_items)
                    end_index = max(grid_window.selected_items + [image_index])
                    grid_window.selected_items = list(range(start_index, end_index + 1))
                else:
                    grid_window.selected_items.append(image_index)
                update_selection(grid_window)
    except Exception as e:
        logging.error(f"Error handling shift-click in GridWindow: {e}")

def update_selection(grid_window):
    for i in range(len(grid_window.images)):
        if i in grid_window.selected_items:
            if i not in grid_window.selection_boxes:
                x, y = grid_window.image_positions[i]
                box = grid_window.canvas.create_rectangle(x, y, x + grid_window.grid_size, y + grid_window.grid_size, outline="green", width=2)
                grid_window.selection_boxes[i] = box
        else:
            if i in grid_window.selection_boxes:
                grid_window.canvas.delete(grid_window.selection_boxes[i])
                del grid_window.selection_boxes[i]

def start_box_select(grid_window, event):
    grid_window.box_select_data["start_x"] = event.x
    grid_window.box_select_data["start_y"] = event.y
    grid_window.box_select_data["rect"] = grid_window.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="green", width=2)

def on_box_select(grid_window, event):
    if grid_window.box_select_data["rect"]:
        grid_window.canvas.coords(grid_window.box_select_data["rect"], grid_window.box_select_data["start_x"], grid_window.box_select_data["start_y"], event.x, event.y)
    update_box_selection(grid_window, event)

def end_box_select(grid_window, event):
    update_box_selection(grid_window, event)
    if grid_window.box_select_data["rect"]:
        grid_window.canvas.delete(grid_window.box_select_data["rect"])
        grid_window.box_select_data["rect"] = None

def update_box_selection(grid_window, event):
    start_x, start_y = grid_window.box_select_data["start_x"], grid_window.box_select_data["start_y"]
    end_x, end_y = event.x, event.y
    if start_x > end_x:
        start_x, end_x = end_x, start_x
    if start_y > end_y:
        start_y, end_y = end_y, start_y
    grid_window.selected_items = []
    for i, (x, y) in enumerate(grid_window.image_positions):
        if start_x <= x <= end_x and start_y <= y <= end_y:
            grid_window.selected_items.append(i)
    update_selection(grid_window)

def delete_selected_files(grid_window):
    try:
        for image_index in sorted(grid_window.selected_items, reverse=True):
            grid_window.images.pop(image_index)
            grid_window.image_paths.pop(image_index)
            if image_index in grid_window.selection_boxes:
                grid_window.canvas.delete(grid_window.selection_boxes[image_index])
                del grid_window.selection_boxes[image_index]
        grid_window.selected_items = []
        display_images(grid_window)
    except Exception as e:
        logging.error(f"Error deleting selected files: {e}")

def apply_grid_size(grid_window, value):
    try:
        logging.debug(f"Applying grid size: {value}")
        grid_window.grid_size = int(value)
        display_images(grid_window)
    except Exception as e:
        logging.error(f"Error applying grid size: {e}")

# --- Click-vs-Drag Logic ---
def handle_image_mouse_down(grid_window, event):
    try:
        item = grid_window.canvas.find_closest(event.x, event.y)
        if item:
            tags = grid_window.canvas.gettags(item)
            if "image" in tags:
                image_index = int(tags[0])
                grid_window._mouse_down_info = {
                    "image_index": image_index,
                    "x": event.x,
                    "y": event.y,
                    "event": event,
                    "drag_started": False,
                    "was_selected": image_index in grid_window.selected_items,
                }
    except Exception as e:
        logging.error(f"Error in handle_image_mouse_down: {e}")

def handle_image_mouse_move(grid_window, event):
    try:
        info = getattr(grid_window, '_mouse_down_info', None)
        if not info or info.get("drag_started"): return
        dx = abs(event.x - info["x"])
        dy = abs(event.y - info["y"])
        if dx > 3 or dy > 3:
            # Start drag
            info["drag_started"] = True
            image_index = info["image_index"]
            # If the pressed image was already selected, drag all selected; else, drag just this one
            if info["was_selected"] and grid_window.selected_items:
                drag_indices = list(grid_window.selected_items)
            else:
                drag_indices = [image_index]
                grid_window.selected_items = [image_index]
                update_selection(grid_window)
            grid_window.drag_data["items"] = [grid_window.canvas.find_withtag(str(i))[0] for i in drag_indices]
            grid_window.drag_data["x"] = event.x
            grid_window.drag_data["y"] = event.y
            grid_window.drag_data["image_indices"] = drag_indices
            grid_window.drag_data["floating_images"] = []
            for image_index in drag_indices:
                image = grid_window.tk_images[image_index]
                floating_image = tk.Toplevel(grid_window)
                floating_image.overrideredirect(True)
                floating_image.geometry(f"+{event.x_root}+{event.y_root}")
                label = tk.Label(floating_image, image=image)
                label.pack()
                grid_window.drag_data["floating_images"].append(floating_image)
            logging.debug(f"Drag started with indices: {drag_indices}")
    except Exception as e:
        logging.error(f"Error in handle_image_mouse_move: {e}")

def handle_image_mouse_up(grid_window, event):
    try:
        info = getattr(grid_window, '_mouse_down_info', None)
        if not info:
            return
        if not info.get("drag_started"):
            # This was a click, not a drag: update selection
            image_index = info["image_index"]
            grid_window.selected_items = [image_index]
            update_selection(grid_window)
        # Clean up
        grid_window._mouse_down_info = None
    except Exception as e:
        logging.error(f"Error in handle_image_mouse_up: {e}")