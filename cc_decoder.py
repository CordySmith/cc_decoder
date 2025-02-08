#!/usr/bin/env python
# coding=utf-8
"""
ccDecoder is a Python Closed Caption Decoder/Extractor
Presented by Max Smith and notonbluray.com

Python 3.7+ compatible

Public domain / Unlicense per license section below
But attribution is always appreciated where possible.

Usage
-----
cc_decoder.py somevideofile.mpg >> somevideofile.srt

A Few Notes
-----------

There are two scripts that make up this tool: A command line interface
(cc_decoder) and a library file (lib.cc_decode).

The library makes the assumption that a stream of images are passed to
it that have closed caption data embedded in the top. It also assumes
that the images are wrapped in a object which will provide standardized
access to it. The library has minimal dependencies, and may be useful
for embedded projects.

The command line interface has many dependencies including PIL (Pillow)
and FFmpeg. Excellent builds of FFMpeg are available at
http://ffmpeg.zeranoe.com/builds/

If you use the command line tool - it's worth providing it with access
to a fast temporary area for writing data to, by default it will use
the system default temporary area, which may share space with your OS.

My primary goal of this project was to extract subtitles from my
Laserdisc collection (mostly simple pop-on mode). I've tried to cover
as much of the Closed Caption spec as possible, but I am limited by a
shortage of test-cases. I would love to get it working on some more
exotic captions (i.e. roll-up, XDS, ITV) but really need some sample
media to work with. If you have media that has these more exotic
captions - please drop me a line via my website (notonbluray.com)
"""

__author__ = "Max Smith"
__copyright__ = "Copyright 2014 Max Smith"
__credits__ = ["Max Smith"]
__license__ = """
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>
"""

from PIL import Image  # Note using Pillow rather than PIL
import atexit
import os
import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import lib.cc_decode
from lib.cc_decode import decode_image_list_to_srt, decode_captions_raw, decode_captions_to_scc, decode_captions_debug
from lib.cc_decode import FileImageWrapper, decode_xds_packets, decode_image_list_to_srt_roll

# Defaults - won't work everywehere, that's why we allow it to be manually set
FFMPEG_LOC = {
    'win32': os.path.join(os.environ["ProgramFiles"], 'ffmpeg', 'ffmpeg.exe'),
    'cygwin': os.path.join(os.environ["ProgramFiles"], 'ffmpeg', 'ffmpeg.exe'),
    'linux2': os.path.join(os.path.sep + 'usr', 'local', 'bin', 'ffmpeg'),
    'darwin': os.path.join(os.path.sep + 'usr', 'local', 'bin', 'ffmpeg'),
}


class PilImageWrapper(FileImageWrapper):
    """ Since we might want to hook the caption decoder up to live streams, etc, decouple the image object from the
        decoding function """

    def __init__(self, filename):
        super(PilImageWrapper, self).__init__(filename)
        img = Image.open(self.file_name)  # .transpose(Image.FLIP_TOP_BOTTOM)
        self.width, self.height = img.size
        if img.size[0] != 720:
            img.resize((720, img.size[1]))  # If the image is not 720px wide, resize
        self.image = img.convert('RGB').load()

    def get_pixel_luma(self, x, y):
        """ Return a pixels luma value normalized to the range 0 (black) to 255 (white) """
        r, g, b, = self.image[int(x), int(y)]
        return (r + g + b) / 3


class ClosedCaptionFileDecoder(object):
    DECODERS = {'srt': decode_image_list_to_srt,
                'srtroll': decode_image_list_to_srt_roll,
                'scc': decode_captions_to_scc,
                'raw': decode_captions_raw,
                'debug': decode_captions_debug,
                'xds': decode_xds_packets}

    def __init__(self, ffmpeg_path=None, temp_path=None, ccformat=None, start_line=0, lines=10, fixed_line=None, ccfilter=0):
        self.ffmpeg_path = ffmpeg_path or FFMPEG_LOC.get(sys.platform)
        self.temp_dir_path = temp_path or tempfile.gettempdir()
        self.format = ccformat or 'srt'
        self.lines = lines
        self.fixed_line = fixed_line
        self.fpid = None
        self.start_line = start_line
        self.workingdir = ''
        self.ccfilter=ccfilter

    def _cleanup(self):
        """ If we terminate unexpectedly, make sure we stop ffmpeg generating files """
        if self.fpid and self.fpid.poll() is None:  # Still running
            self.fpid.kill()
        if self.workingdir:
            shutil.rmtree(self.workingdir)

    def stream_decode_file_list(self, input_file, start_line=0, lines=5, image_wrapper=None):
        """ Returns a generator of image objects based on ffmpeg decoding the top 10 lines of the passed input_file.
            Run ffmpeg in a subprocess generating tiffs of the video frame until ffmpeg finishes and we run out of
            frames.
             input_file - input video file. Anything that ffmpeg understands
             tempdir    - where to write the tiffs to, ideally somewhere that can sustain high throughput, and has space
             start_line - the line number to start capturing (default 0)
             lines      - the number of lines to write to the tiff, counting from the start line (default 5)
             image_wrapper - the class to wrap the image file name with, default is PilImageWrapper """

        if not os.path.exists(self.ffmpeg_path):
            raise RuntimeError('Could not find ffmpeg at %s' % self.ffmpeg_path)
        image_wrapper = image_wrapper or PilImageWrapper
        self.workingdir = tempfile.mkdtemp(dir=self.temp_dir_path)
        tempfile_name_structure = 'ccdecode%07d.tif'
        ffmpeg_cmd = '%s -i "%s" -vf "scale=720:ih, crop=iw:%d:0:%d" -pix_fmt rgb24 -f image2 "%s"' % \
                     (self.ffmpeg_path, input_file, start_line + lines, start_line,
                      os.path.join(self.workingdir, tempfile_name_structure))

        def next_file_name(file_num):
            return os.path.join(self.workingdir, (tempfile_name_structure % file_num))

        with open(os.devnull, 'wb') as devnull:
            atexit.register(self._cleanup)
            self.fpid = subprocess.Popen(ffmpeg_cmd, stderr=devnull)
            file_number = 1
            while self.fpid.poll() is None:  # While ffmpeg is running
                if os.path.exists(next_file_name(file_number)) and os.path.exists(next_file_name(file_number + 1)):
                    # Latch on the existence of the n+1 file, which wouldn't exist until the n file is fully written
                    yield image_wrapper(next_file_name(file_number))
                    file_number += 1
                else:
                    time.sleep(0.25)  # Take a nap for a moment, since we must have caught up with FFMpeg
        # FFMpeg must have exited - process all remaining files
        self.fpid = None
        while os.path.exists(next_file_name(file_number)):
            yield image_wrapper(next_file_name(file_number))
            file_number += 1
        os.rmdir(self.workingdir)
        self.workingdir = ''

    def decode(self, filename):
        imagewrapper_generator = self.stream_decode_file_list(
            filename, lines=self.lines, start_line=self.start_line)

        if self.format in self.DECODERS:
            decoder_func = self.DECODERS.get(self.format)
            decoder_func(imagewrapper_generator, ccfilter=self.ccfilter)
        else:
            raise RuntimeError('Unknown output format %s, try one of %s' % (format, self.DECODERS.keys()))


def main():
    p = argparse.ArgumentParser(description='Extract visible closed captions in a video file')

    ffmpeg = FFMPEG_LOC.get(sys.platform, '')
    tempdir = tempfile.gettempdir()
    p.add_argument('videofile', help='Input video file name')
    p.add_argument('--ffmpeg', default=ffmpeg, help='Path to a copy of the ffmpeg binary (default %s)' % ffmpeg)
    p.add_argument('--temp', default=tempdir, help='Path to temporary working area (default %s)' % tempdir)
    p.add_argument('--ccformat', default='srt', help='Output format xds, srt, scc, srtroll or debug (default srt)')
    p.add_argument('--lines', default=3, type=int,
        help='Number of lines to search for CC in the video, starting at the start line (default 3)')
    p.add_argument('--start_line', default=0, type=int, help='Start at a particular line 0=topmost line')
    p.add_argument('--ccfilter', default=0, type=int,
        help='Filter for a particular closed caption stream 1=CC1, 2=CC2, etc. Only honored in srt mode (default 0=All)')
    p.add_argument('--bitlevel', default=80, type=int,
        help='The R+G+B/3 level that ccdecode reads as "1". 97 according to spec (50 IRE +/- 12 = 38 IRE),' +
            'but we default to 80 (29 IRE) which is seems to work well, adjust lower if your source material is dim.')

    args = p.parse_args()

    # Prime stdout for unicode UTF-8 output
    sys.stdout.reconfigure(encoding='utf-8')

    # Set video level
    lib.cc_decode.LUMA_THRESHOLD = args.bitlevel

    if args.videofile:
        decoder = ClosedCaptionFileDecoder(ffmpeg_path=args.ffmpeg, temp_path=args.temp, ccformat=args.ccformat,
                                           lines=args.lines, start_line=args.start_line, ccfilter=args.ccfilter)
        decoder.decode(args.videofile)

main()