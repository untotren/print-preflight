"""Image loading and background/content masking (Pillow only)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError

from .errors import PreflightError

SUPPORTED_FORMATS = frozenset({"PNG", "JPEG", "TIFF"})

# A pixel is background when it is fully transparent, or when all of its
# R, G and B channels are >= this value (unprinted paper white, with headroom
# for JPEG noise).
WHITE_MIN = 250


def to_rgba(im: Image.Image) -> Image.Image:
    if im.mode.startswith("I;16") or im.mode in ("I", "F"):
        # High bit depth greyscale: scale 16-bit range down to 8 bits.
        im = im.convert("I").point(lambda v: v * (1 / 256)).convert("L")
    return im.convert("RGBA")


def load_image(path: str | Path) -> Image.Image:
    """Open a PNG/JPEG/TIFF, apply EXIF orientation, return an RGBA copy."""
    try:
        with Image.open(path) as im:
            if im.format not in SUPPORTED_FORMATS:
                raise PreflightError(
                    "UNSUPPORTED_FORMAT",
                    f"{path}: format {im.format} is not one of PNG, JPEG, TIFF",
                )
            im.load()
            return to_rgba(ImageOps.exif_transpose(im))
    except FileNotFoundError:
        raise PreflightError("IMAGE_NOT_FOUND", f"image not found: {path}") from None
    except IsADirectoryError:
        raise PreflightError("IMAGE_UNREADABLE", f"{path} is a directory") from None
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise PreflightError("IMAGE_UNREADABLE", f"cannot decode {path}: {exc}") from None


def content_mask(rgba: Image.Image) -> Image.Image:
    """Mode ``L`` mask: 255 where the pixel is content, 0 where background."""
    r, g, b, a = rgba.split()

    def is_white(ch: Image.Image) -> Image.Image:
        return ch.point(lambda v: 255 if v >= WHITE_MIN else 0)

    white = ImageChops.multiply(ImageChops.multiply(is_white(r), is_white(g)), is_white(b))
    opaque = a.point(lambda v: 255 if v > 0 else 0)
    # opaque AND NOT white (subtract clamps at 0)
    return ImageChops.subtract(opaque, white)


def count_content(mask: Image.Image, box: tuple[int, int, int, int]) -> int:
    return mask.crop(box).histogram()[255]
