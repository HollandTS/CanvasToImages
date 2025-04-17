import struct
from PIL import Image

class TemFile:
    def __init__(self, file_path):
        self.file_path = file_path
        with open(file_path, 'rb') as f:
            self.data = bytearray(f.read())
        self.width = struct.unpack_from('<H', self.data, 0)[0]
        self.height = struct.unpack_from('<H', self.data, 2)[0]
        self.main_img_offset = struct.unpack_from('<I', self.data, 12)[0]
        self.main_img_size = struct.unpack_from('<I', self.data, 16)[0]

    def get_main_image(self):
        img_data = self.data[self.main_img_offset:self.main_img_offset + self.width * self.height]
        return Image.frombytes('P', (self.width, self.height), bytes(img_data))

    def set_main_image(self, pil_image):
        # Assumes pil_image is mode 'P' and same size
        img_bytes = pil_image.tobytes()
        if len(img_bytes) != self.width * self.height:
            raise ValueError("Image size mismatch")
        self.data[self.main_img_offset:self.main_img_offset + self.width * self.height] = img_bytes

    def save(self, out_path=None):
        with open(out_path or self.file_path, 'wb') as f:
            f.write(self.data)
