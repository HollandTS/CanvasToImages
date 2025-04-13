from PIL import Image, ImageEnhance, ImageDraw
import logging
import io
import subprocess

def apply_transparency(image, color):
    try:
        logging.info(f"Applying transparency to image with color: {color}")
        image = image.convert("RGBA")
        datas = image.getdata()
        new_data = []
        for item in datas:
            if item[:3] == color:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        image.putdata(new_data)
        logging.info("Transparency applied successfully")
        return image
    except Exception as e:
        logging.error(f"Error applying transparency: {e}")
        return image

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

def convert_image_to_rgba(image):
    try:
        image = image.convert("RGBA")
        alpha = ImageEnhance.Brightness(image.split()[3]).enhance(1.0)
        image.putalpha(alpha)
        logging.info("Image converted to RGBA")
        return image
    except Exception as e:
        logging.error(f"Error converting image to RGBA: {e}")
        return image

def paste_image(base_image, overlay_image, position):
    try:
        base_image.paste(overlay_image, position, overlay_image)
        logging.info("Image pasted successfully")
        return base_image
    except Exception as e:
        logging.error(f"Error pasting image: {e}")
        return base_image

def capture_canvas_image(canvas, images, item=None):
    try:
        canvas.update()
        if item:
            x0, y0, x1, y1 = canvas.bbox(item)
            ps_image = canvas.postscript(colormode='color', x=x0, y=y0, width=x1-x0, height=y1-y0)
        else:
            ps_image = canvas.postscript(colormode='color')
        process = subprocess.Popen(['gswin64c', '-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=pngalpha', '-sOutputFile=-', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        image_data, _ = process.communicate(ps_image.encode('utf-8'))
        image = Image.open(io.BytesIO(image_data)).convert("RGBA")
        logging.info("Canvas image captured successfully")
        return image
    except Exception as e:
        logging.error(f"Error capturing canvas image: {e}")
        return None

def save_image(image, file_path):
    try:
        image.save(file_path)
        logging.info(f"Image saved to {file_path}")
    except Exception as e:
        logging.error(f"Error saving image: {e}")

def load_image(file_path):
    try:
        image = Image.open(file_path).convert("RGBA")
        logging.info(f"Image loaded from {file_path}")
        return image
    except Exception as e:
        logging.error(f"Error loading image: {e}")
        return None