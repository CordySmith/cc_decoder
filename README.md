cc_decoder
==========
ccDecoder is a Python Closed Caption Decoder/Extractor
Presented by Max Smith and notonbluray.com

Python 2.7+ and Python 3 compatible

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

cc_decoder.py somevideofile.mpg >> somevideofile.srt
 Extract subtitles in SRT format
cc_decoder.py --ccformat scc somevideofile.mpg >> somevideofile.scc
 Extract subtitles in SCC format
cc_decoder.py --ccformat xds somevideofile.mpg >> somevideofile.txt
 Extract XDS information

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
