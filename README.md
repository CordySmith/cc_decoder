cc_decoder
==========
ccDecoder is a Python based Closed Caption Decoder/Extractor for
extracting line 21 closed caption embedded in video recordings.

Presented by Max Smith and notonbluray.com

Python 3.6+ compatible

Public domain / Unlicense per license section below
But attribution is always appreciated where possible.

My primary goal of this project was to extract subtitles from my
Laserdisc collection (mostly simple pop-on mode). I've tried to cover
as much of the Closed Caption spec as possible, but I am limited by a
shortage of test-cases. I would love to get it working on some more
exotic captions (i.e. roll-up, XDS, ITV) but really need some sample
media to work with. If you have media that has these more exotic
captions - please drop me a line via my website (notonbluray.com)

Usage
=====

`cc_decoder.py somevideofile.mpg >> somevideofile.srt`

 Extract subtitles in SRT format
 
`cc_decoder.py --ccformat scc somevideofile.mpg >> somevideofile.scc`

 Extract subtitles in SCC format
 
`cc_decoder.py --ccformat xds somevideofile.mpg >> somevideofile.txt`

 Extract XDS information
 
`cc_decoder.py --ccfilter 1 somevideofile.mpg >> somevideofile.txt`

 Extract only CC1 subtitles in SRT format
 
`cc_decoder.py --bitlevel 60 dim_video_file.mkv >> dim_video_file.srt`

 Extract all subtitles in SRT format, assuming a 0->1 transition level of 60.

Performance
===========
About 10-20x realtime on my i7 machine. Primarily limited by FFMpeg
throughput.

A Few Notes
===========

There are two scripts that make up this tool: A command line interface
(cc_decoder) and a library file (lib.cc_decode).

The library makes the assumption that a stream of images are passed to
it that have closed caption data embedded in the top. It also assumes
that the images are wrapped in a object which will provide standardized
access to it. The library has minimal dependencies, and may be useful
for an embedded project.

The command line interface has many dependencies including PIL (Pillow)
and FFmpeg. Excellent builds of FFMpeg are available at
http://ffmpeg.zeranoe.com/builds/

If you use the command line tool - it's worth providing it with access
to a fast temporary area for writing data to, by default it will use
the system default temporary area, which may share space with your OS.

Building Standalone.exe with Pyinstaller
========================================

Pyinstaller creates nice standalone .exe files for windows and beyond.

pyinstaller --clean --onefile --console --exclude-module numpy --exclude-module scipy --upx-dir="c:\Program Files\UPX" cc_decoder.py

Version History
===============

1.0 Technical the second version
 * SCC decoding

2.0 Tenth anniversary edition
 * "Upgraded" codebase to Python 3.x
 * Allow overriding 0->1 LUMA level (default = 80, spec=~~97) with --bitlevel
 * Support for filtering CC1/CC2 streams with --ccfilter
 * Improved SRT output format (added running count for subtitles)
 * Some (limited) extended language support for other regions
 * XDS date/time transmission decoding
 * Stdout is forced to UTF-8 to support extended symbols

