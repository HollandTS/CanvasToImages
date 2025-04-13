from PIL import Image

class ImageLoader:
    @staticmethod
    def load_image(file_path):
        return Image.open(file_path)