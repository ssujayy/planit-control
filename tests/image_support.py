"""Real, small encoded images for upload behavior checks."""
import io
from PIL import Image


def image_bytes(kind='PNG'):
    stream = io.BytesIO()
    Image.new('RGB', (8, 8), (30, 100, 70)).save(stream, format=kind)
    return stream.getvalue()


PNG, JPEG, WEBP = (image_bytes(kind) for kind in ('PNG', 'JPEG', 'WEBP'))
