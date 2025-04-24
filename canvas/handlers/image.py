import logging
import uuid
from PIL import Image, ImageTk

class ImageHandler:
    def __init__(self, canvas_window):
        self.canvas_window = canvas_window
        self.next_z_index = 1
        
    def add_image(self, image_path, x, y, image_id=None):
        """Add an image to the canvas at the specified position."""
        try:
            # Load and convert image
            pil_image = Image.open(image_path)
            tk_image = ImageTk.PhotoImage(pil_image)
            
            # Keep reference to prevent garbage collection
            self.canvas_window.tk_images.append(tk_image)
            
            # Determine z-index based on layer_behind setting
            if self.canvas_window.layer_behind:
                # Place behind existing images
                min_z = min([data.get('z_index', 0) for data in self.canvas_window.images.values()]) if self.canvas_window.images else 0
                z_index = min_z - 1
            else:
                # Place on top
                z_index = self.next_z_index
                self.next_z_index += 1
            
            # Create unique ID if not provided
            if image_id is None:
                image_id = str(uuid.uuid4())
            
            # Store image data
            self.canvas_window.images[image_path] = {
                'image': tk_image,
                'pil_image': pil_image,
                'x': x,
                'y': y,
                'id': image_id,
                'z_index': z_index
            }
            
            # Create canvas item
            self.canvas_window.canvas.create_image(x, y, image=tk_image, anchor="nw", tags=("image", image_id))
            
            # Update canvas
            self.canvas_window.redraw_canvas()
            
            return image_id
            
        except Exception as e:
            logging.error(f"Error adding image: {e}", exc_info=True)
            return None 