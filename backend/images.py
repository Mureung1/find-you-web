from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTOS = 4
MAX_PIXELS = 24_000_000
PHOTO_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def sanitize_photo(data: bytes, declared_type: str | None = None) -> bytes:
    if not data or len(data) > MAX_PHOTO_BYTES:
        raise ValueError("사진은 장당 8MB 이하로 올려 주세요.")
    try:
        with Image.open(BytesIO(data), formats=list(PHOTO_TYPES)) as source:
            actual_type = PHOTO_TYPES.get(source.format or "")
            if actual_type is None or (declared_type and actual_type != declared_type):
                raise ValueError("JPEG, PNG 또는 WebP 사진을 선택해 주세요.")
            if source.width * source.height > MAX_PIXELS or getattr(source, "is_animated", False):
                raise ValueError("2,400만 화소 이하의 정지 사진을 선택해 주세요.")
            oriented = ImageOps.exif_transpose(source).convert("RGBA")
            oriented.thumbnail((2000, 2000))
            clean = Image.new("RGB", oriented.size, "white")
            clean.paste(oriented, mask=oriented.getchannel("A"))
            output = BytesIO()
            clean.save(output, format="JPEG", quality=86, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("사진을 읽을 수 없어요. JPEG, PNG 또는 WebP 사진을 선택해 주세요.") from error
