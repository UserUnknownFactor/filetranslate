# -*- coding: utf-8 -*-
"""
    maxcolor
"""
__version__ = '0.3.0'

import math, io
from PIL import Image

class MaxColor(object):
    """MaxColor main class."""

    white_threshold = 200 # If pixel is almost white
    black_threshold = 100 # If pixel is almost black
    alpha_threshold = 100 # If pixel is kind of opaque

    def __init__(self, input_stream, default_color=None):
        """Create one class for one image.

        :param input_stream: A filename (string) or a file object or Image or raw RGBA pixel list.
        :param default_color: color to use if no matches found: (0xFF,0xFF,0xFF), None, etc.
        """
        self.image = None
        self.pixels = None
        self.cmap = None
        self.default_color = default_color
        if (isinstance(input_stream, str) or isinstance(input_stream, io.BufferedIOBase) or
            isinstance(input_stream, io.RawIOBase) or isinstance(input_stream, io.IOBase)):
            self.image = Image.open(input_stream)
        elif isinstance(input_stream, Image.Image):
            self.image = input_stream
        elif isinstance(input_stream, list):
             self.pixels = input_stream
        else:
            raise "Not an image-like parameter"

    @staticmethod
    def hex_to_rgb(hex):
        return tuple(bytes.fromhex(hex.replace("#", ''))[:3])

    @staticmethod
    def rgb_to_hex(r, g, b):
        return '#{:02X}{:02X}{:02X}'.format(r, g, b)

    @staticmethod
    def pix_to_hex(pix):
        if not pix or len(pix)<3: return (0, 0, 0)
        return MaxColor.rgb_to_hex(pix[0], pix[1], pix[2])

    @staticmethod
    def hilo(a, b, c):
        if c < b: b, c = c, b
        if b < a: a, b = b, a
        if c < b: b, c = c, b
        return a + c

    @staticmethod
    def is_white(r, g, b):
        return (r > MaxColor.white_threshold and
                g > MaxColor.white_threshold and
                b > MaxColor.white_threshold)

    @staticmethod
    def is_black(r, g, b):
        return (r < MaxColor.black_threshold and
                g < MaxColor.black_threshold and
                b < MaxColor.black_threshold)

    @staticmethod
    def complement_pix(pix):
        if not pix or len(pix)<3: return (0, 0, 0)
        return MaxColor.complement(pix[0], pix[1], pix[2])

    @staticmethod
    def complement(r, g, b):
        k = MaxColor.hilo(r, g, b)
        if MaxColor.is_white(r, g, b):
            return (0, 0, 0)
        elif MaxColor.is_black(r, g, b):
            return (0xff, 0xff, 0xff)
        return tuple(k - u for u in (r, g, b))

    def get_color(self, quality=1, no_white=True, no_black=True, dist=False):
        """Get the dominant color.

        :param quality: quality settings, 1 is the highest quality, the bigger
                        the number, the faster a color will be returned but
                        the greater the likelihood that it will not be the
                        visually most dominant color
        :param no_white: ignore white pixels if True
        :param no_black: ignore black pixels if True
        :param dist: return pixel with its frequency if True
        :return tuple: (r, g, b)
        """
        palette = self.get_palette(5, quality, no_white=no_white, no_black=no_black, dist=dist)
        return palette[0]

    def get_palette(self, color_count=10, quality=1, no_white=True, no_black=True, dist=False):
        """Build a color palette.  We are using the median cut algorithm to
        cluster similar colors.

        :param color_count: the size of the palette, max number of colors
        :param quality: quality settings, 1 is the highest quality, the bigger
                        the number, the faster the palette generation, but the
                        greater the likelihood that colors will be missed.
        :param no_white: ignore white pixels if True
        :param no_black: ignore black pixels if True
        :param dist: return pixels with their distribution if True
        :return list: a list of tuples in the (r, g, b) form
        """
        if self.image:
            image = self.image.convert('RGBA')
            width, height = image.size
            self.pixels = image.getdata()
            pixel_count = width * height
        else:
            pixel_count = len(self.pixels)
        valid_pixels = []
        for i in range(0, pixel_count, quality):
            r, g, b, a = self.pixels[i]
            if a >= self.alpha_threshold:
                is_white = self.is_white(r, g, b)
                is_black = self.is_black(r, g, b)
                if (no_white and no_black) and not (is_white or is_black):
                    valid_pixels.append((r, g, b))
                elif no_black and not is_black:
                    valid_pixels.append((r, g, b))
                elif no_white and not is_white:
                    valid_pixels.append((r, g, b))
                elif (not no_white and not no_black):
                    valid_pixels.append((r, g, b))

        if len(valid_pixels) == 0:
            return [self.default_color]

        distribution = dict()
        for pixel in valid_pixels:
            if pixel in distribution: distribution[pixel] += 1
            else: distribution[pixel] = 1
        distribution = list(distribution)
        distribution.sort(reverse=True)
        return distribution[:color_count]