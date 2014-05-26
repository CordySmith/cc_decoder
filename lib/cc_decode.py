#!/usr/local/bin/python
# coding: utf-8
"""
ccDecoder is a Python Closed Caption Decoder.
Presented by Max Smith and notonbluray.com

Python 2.7+ and Python 3 compatible

Public domain / Unlicense
But attribution is always appreciated where possible.

See spec: http://www.gpo.gov/fdsys/pkg/CFR-2007-title47-vol1/pdf/CFR-2007-title47-vol1-sec15-119.pdf
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
__version__ = "1.0.0"
__maintainer__ = "Max Smith"
__email__ = None  # Sorry, I get far too much spam as it is. Track me down at http://www.notonbluray.com

import os

# Assumes 27 pixel wide 'bit' starting at pixel 280 - assumes 720 pixel wide video (enforced elsewhere)
# Odd parity on the rightmost bit, we sample central pixels of the bit and average
BYTE1_LOCATIONS = [285 + (i * 27) for i in range(0, 8)]
BYTE2_LOCATIONS = [285 + (i * 27) for i in range(8, 16)]

# Sine wave preamble indicates presence of captions
SYNC_SIGNAL_LOCATIONS_HIGH = [28 + (i * 27) for i in range(0, 7)]  # White
SYNC_SIGNAL_LOCATIONS_LOW = [14 + (i * 27) for i in range(0, 7)]   # Black

# When searching for preamble - search in this range
PREAMBLE_SCAN_RANGE = range(-13, 30)

# Bit value of 1 above this 'luma' level, 0 below
LUMA_THRESHOLD = 80

CC_TABLE = {
    0x00: '',  # Special - included here to clear a few things up
    0x20: ' ', 0x21: '!', 0x22: '"', 0x23: '#', 0x24: '$', 0x25: '%', 0x26: '&', 0x27: "'", 0x28: "(", 0x29: ")",
    0x2A: 'á', 0x2B: '+', 0x2C: ',', 0x2D: '-', 0x2E: '.', 0x2F: '/', 0x3A: ':', 0x3B: ';', 0x3C: '<', 0x3D: '=',
    0x3E: '>', 0x3F: '?', 0x40: '@', 0x5B: '[', 0x5C: 'é', 0x5D: ']', 0x5E: 'í', 0x5F: 'ó', 0x60: 'ú', 0x7B: 'ç',
    0x7C: '÷', 0x7D: 'Ñ', 0x7E: 'ñ', 0x7F: '■',
}

# Populate standard ASCII codes ASCII ranges that are shared
CC_TABLE.update({i: chr(i) for nr in [(0x41, 0x5B), (0x61, 0x7B), (0x30, 0x3A)] for i in range(nr[0], nr[1])})

# Two byte chars
SPECIAL_CHARS_TABLE = {
    0x30: '®', 0x31: '°', 0x32: '½', 0x33: '¿', 0x34: '™', 0x35: '¢', 0x36: '£', 0x37: '♪',
    0x38: 'à', 0x39: ' ', 0x3A: 'è', 0x3B: 'â', 0x3C: 'ê', 0x3D: 'î', 0x3E: 'ô', 0x3F: 'û',
}

CC1_SPECIAL_CHARS_TABLE = {(0x11, a): b for (a, b) in SPECIAL_CHARS_TABLE.items()}
CC2_SPECIAL_CHARS_TABLE = {(0x19, a): b for (a, b) in SPECIAL_CHARS_TABLE.items()}
# Achieving compatibility with Python2 and 3 makes us do strange things
ALL_SPECIAL_CHARS = CC1_SPECIAL_CHARS_TABLE.copy()
ALL_SPECIAL_CHARS.update(CC2_SPECIAL_CHARS_TABLE)

CONTROL_CODES = {
    (0x14, 0x20): 'Resume Caption Loading',     (0x14, 0x21): 'Backspace',
    (0x14, 0x22): 'Reserved (Alarm Off)',       (0x14, 0x23): 'Reserved (Alarm On)',
    (0x14, 0x24): 'Delete to End Of Row',       (0x14, 0x25): 'Roll-Up Captions-2 Rows',
    (0x14, 0x26): 'Roll-Up Captions-3 Rows',    (0x14, 0x27): 'Roll-Up Captions-4 Rows',
    (0x14, 0x28): 'Flash On',                   (0x14, 0x29): 'Resume Direct Captioning',
    (0x14, 0x2A): 'Text Restart',               (0x14, 0x2B): 'Resume Text Display',
    (0x14, 0x2C): 'Erase Displayed Memory',     (0x14, 0x2D): 'Carriage Return',
    (0x14, 0x2E): 'Erase Non-Displayed Memory', (0x14, 0x2F): 'End of Caption (flip memory)',
    (0x17, 0x21): 'Tab Offset 1',               (0x17, 0x22): 'Tab Offset 2',
    (0x17, 0x23): 'Tab Offset 3',
}

MID_ROW_CODES = {
    (0x11, 0x20): 'Mid-row: White',   (0x11, 0x21): 'Mid-row: White Underline',
    (0x11, 0x22): 'Mid-row: Green',   (0x11, 0x23): 'Mid-row: Green Underline',
    (0x11, 0x24): 'Mid-row: Blue',    (0x11, 0x25): 'Mid-row: Blue Underline',
    (0x11, 0x26): 'Mid-row: Cyan',    (0x11, 0x27): 'Mid-row: Cyan Underline',
    (0x11, 0x28): 'Mid-row: Red',     (0x11, 0x29): 'Mid-row: Red Underline',
    (0x11, 0x2A): 'Mid-row: Yellow',  (0x11, 0x2B): 'Mid-row: Yellow Underline',
    (0x11, 0x2C): 'Mid-row: Magenta', (0x11, 0x2D): 'Mid-row: Magenta Underline',
    (0x11, 0x2E): 'Mid-row: Italics', (0x11, 0x2F): 'Mid-row: Italics Underline',
}

## Preamble for odd columns except where it isn't
PREAMBLE_ODD = {
    0x40: 'Pre: White',         0x41: 'Pre: White Underline',
    0x42: 'Pre: Green',         0x43: 'Pre: Green Underline',
    0x44: 'Pre: Blue',          0x45: 'Pre: Blue Underline',
    0x46: 'Pre: Cyan',          0x47: 'Pre: Cyan Underline',
    0x48: 'Pre: Red',           0x49: 'Pre: Red Underline',
    0x4A: 'Pre: Yellow',        0x4B: 'Pre: Yellow Underline',
    0x4C: 'Pre: Magenta',       0x4D: 'Pre: Magenta Underline',
    0x4E: 'Pre: White Italics', 0x4F: 'Pre: White Italics Underline',
    0x50: 'Pre: Indent 0',      0x51: 'Pre: Indent 0 Underline',
    0x52: 'Pre: Indent 4',      0x53: 'Pre: Indent 4 Underline',
    0x54: 'Pre: Indent 8',      0x55: 'Pre: Indent 8 Underline',
    0x56: 'Pre: Indent 12',     0x57: 'Pre: Indent 12 Underline',
    0x58: 'Pre: Indent 16',     0x59: 'Pre: Indent 16 Underline',
    0x5A: 'Pre: Indent 20',     0x5B: 'Pre: Indent 20 Underline',
    0x5C: 'Pre: Indent 24',     0x5D: 'Pre: Indent 24 Underline',
    0x5E: 'Pre: Indent 28',     0x5F: 'Pre: Indent 28 Underline',
}
EVEN_PREAMBLE = {a + 0x20: b for (a, b) in PREAMBLE_ODD.items()}

CC1_CONTROL_CODES = {(a[0], a[1]): 'CC1 ' + b for (a, b) in CONTROL_CODES.items()}
CC2_CONTROL_CODES = {(a[0] == 0x14 and 0x1C or 0x1F, a[1]): 'CC2 ' + b for (a, b) in CONTROL_CODES.items()}
CC1_MID_ROW_CODES = {(0x11, a[1]): 'CC1 ' + b for (a, b) in MID_ROW_CODES.items()}
CC2_MID_ROW_CODES = {(0x19, a[1]): 'CC2 ' + b for (a, b) in MID_ROW_CODES.items()}

## Columns headings 
CC1_PREAMBLE_COLS = [0x11, 0x11, 0x12, 0x12, 0x15, 0x15, 0x16, 0x16, 0x17, 0x17, 0x10, 0x13, 0x13, 0x14, 0x14]
CC2_PREAMBLE_COLS = [0x19, 0x19, 0x1A, 0x1A, 0x1D, 0x1D, 0x1E, 0x1E, 0x1F, 0x1F, 0x18, 0x1B, 0x1B, 0x1C, 0x1C]

COL_PREAMBLE = [PREAMBLE_ODD, EVEN_PREAMBLE, PREAMBLE_ODD, EVEN_PREAMBLE, PREAMBLE_ODD, EVEN_PREAMBLE,
                PREAMBLE_ODD, EVEN_PREAMBLE, PREAMBLE_ODD, EVEN_PREAMBLE, PREAMBLE_ODD, PREAMBLE_ODD,  # Candance change
                EVEN_PREAMBLE, PREAMBLE_ODD, EVEN_PREAMBLE]


def _cc_preamble_table():
    """ Function generated due to complexity - it could be a list comp, but it'd be ugly """
    table = dict()
    for col, val in enumerate(COL_PREAMBLE):
        for (row_code, text) in val.items():
            table[(CC1_PREAMBLE_COLS[col], row_code)] = 'CC1 %s row %d' % (text, (col + 1))
            table[(CC2_PREAMBLE_COLS[col], row_code)] = 'CC2 %s row %d' % (text, (col + 1))
    return table

# Achieving compatibility with Python2 and 3 makes us do strange things
ALL_CC_CONTROL_CODES = _cc_preamble_table()
ALL_CC_CONTROL_CODES.update(CC1_CONTROL_CODES)
ALL_CC_CONTROL_CODES.update(CC2_CONTROL_CODES)
ALL_CC_CONTROL_CODES.update(CC1_MID_ROW_CODES)
ALL_CC_CONTROL_CODES.update(CC2_MID_ROW_CODES)

NO_PARITY_TO_ODD_PARITY = [
    0x80, 0x01, 0x02, 0x83, 0x04, 0x85, 0x86, 0x07, 0x08, 0x89, 0x8a, 0x0b, 0x8c, 0x0d, 0x0e, 0x8f,
    0x10, 0x91, 0x92, 0x13, 0x94, 0x15, 0x16, 0x97, 0x98, 0x19, 0x1a, 0x9b, 0x1c, 0x9d, 0x9e, 0x1f,
    0x20, 0xa1, 0xa2, 0x23, 0xa4, 0x25, 0x26, 0xa7, 0xa8, 0x29, 0x2a, 0xab, 0x2c, 0xad, 0xae, 0x2f,
    0xb0, 0x31, 0x32, 0xb3, 0x34, 0xb5, 0xb6, 0x37, 0x38, 0xb9, 0xba, 0x3b, 0xbc, 0x3d, 0x3e, 0xbf,
    0x40, 0xc1, 0xc2, 0x43, 0xc4, 0x45, 0x46, 0xc7, 0xc8, 0x49, 0x4a, 0xcb, 0x4c, 0xcd, 0xce, 0x4f,
    0xd0, 0x51, 0x52, 0xd3, 0x54, 0xd5, 0xd6, 0x57, 0x58, 0xd9, 0xda, 0x5b, 0xdc, 0x5d, 0x5e, 0xdf,
    0xe0, 0x61, 0x62, 0xe3, 0x64, 0xe5, 0xe6, 0x67, 0x68, 0xe9, 0xea, 0x6b, 0xec, 0x6d, 0x6e, 0xef,
    0x70, 0xf1, 0xf2, 0x73, 0xf4, 0x75, 0x76, 0xf7, 0xf8, 0x79, 0x7a, 0xfb, 0x7c, 0xfd, 0xfe, 0x7f,
]

US_TV_PARENTAL_GUIDELINE_RATING = ['Not rated', 'TV-Y', 'TV-Y7', 'TV-G', 'TV-PG', 'TV-14', 'TV-MA', 'Not rated']

MPA_RATING = ['N/A', 'G', 'PG', 'PG-13', 'R', 'NC-17', 'X', 'Not Rated']

CANADIAN_ENGLISH_RATINGS = ['E', 'C', 'C8+', 'G', 'PG', '14+', '18+', 'Invalid']
CANADIAN_FRENCH_RATINGS = ['E', 'G', '8 ans +', '13 ans +', '16 ans +', '18 ans +', 'Invalid', 'Invalid']


# For rating TV-Y7, Violence becomes fantasy violence
VCHIP_FLAGS_BYTE1 = [(0x20, 'Sexually suggestive dialog')]
VCHIP_FLAGS_BYTE2 = [(0x20, 'Violence'), (0x10, 'Sexual situations'), (0x08, 'Strong language')]

XDS_GENRE_CODES = {
    0x20: 'Education',    0x21: 'Entertainment', 0x22: 'Movie',       0x23: 'News',          0x24: 'Religious',
    0x25: 'Sports',       0x26: 'Other',         0x27: 'Action',      0x28: 'Advertisement', 0x29: 'Animated',
    0x2A: 'Anthology',    0x2B: 'Automobile',    0x2C: 'Awards',      0x2D: 'Baseball',      0x2E: 'Basketball',
    0x2F: 'Bulletin',     0x30: 'Business',      0x31: 'Classical',   0x32: 'College',       0x33: 'Combat',
    0x34: 'Comedy',       0x35: 'Commentary',    0x36: 'Concert',     0x37: 'Consumer',      0x38: 'Contemporary',
    0x39: 'Crime',        0x3A: 'Dance',         0x3B: 'Documentary', 0x3C: 'Drama',         0x3D: 'Elementary',
    0x3E: 'Erotica',      0x3F: 'Exercise',      0x40: 'Fantasy',     0x41: 'Farm',          0x42: 'Fashion',
    0x43: 'Fiction',      0x44: 'Food',          0x45: 'Football',    0x46: 'Foreign',       0x47: 'Fund Raiser',
    0x48: 'Game/Quiz',    0x49: 'Garden',        0x4A: 'Golf',        0x4B: 'Government',    0x4C: 'Health',
    0x4D: 'High School',  0x4E: 'History',       0x4F: 'Hobby',       0x50: 'Hockey',        0x51: 'Home',
    0x52: 'Horror',       0x53: 'Information',   0x54: 'Instruction', 0x55: 'International', 0x56: 'Interview',
    0x57: 'Language',     0x58: 'Legal',         0x59: 'Live',        0x5A: 'Local',         0x5B: 'Math',
    0x5C: 'Medical',      0x5D: 'Meeting',       0x5E: 'Military',    0x5F: 'Miniseries',    0x60: 'Music',
    0x61: 'Mystery',      0x62: 'National',      0x63: 'Nature',      0x64: 'Police',        0x65: 'Politics',
    0x66: 'Premier',      0x67: 'Prerecorded',   0x68: 'Product',     0x69: 'Professional',  0x6A: 'Public',
    0x6B: 'Racing',       0x6C: 'Reading',       0x6D: 'Repair',      0x6E: 'Repeat',        0x6F: 'Review',
    0x70: 'Romance',      0x71: 'Science',       0x72: 'Series',      0x73: 'Service',       0x74: 'Shopping',
    0x75: 'Soap',         0x76: 'Special',       0x77: 'Suspense',    0x78: 'Talk',          0x79: 'Technical',
    0x7A: 'Tennis',       0x7B: 'Travel',        0x7C: 'Variety',     0x7D: 'Video',         0x7E: 'Weather',
    0x7F: 'Western',
}

XDS_AUDIO_SERVICES_LANGUAGE = ['Unknown', 'English', 'Spanish', 'French', 'German', 'Italian', 'Other', 'None']

XDS_AUDIO_SERVICES_TYPE_MAIN = [
    'Unknown', 'Mono', 'Simulated Stereo', 'Stereo', 'Stereo Surround', 'Data Service', 'Other', 'None'
]

XDS_AUDIO_SERVICES_TYPE_SECONDARY = list(XDS_AUDIO_SERVICES_TYPE_MAIN)
XDS_AUDIO_SERVICES_TYPE_SECONDARY[2] = 'Video Descriptions'
XDS_AUDIO_SERVICES_TYPE_SECONDARY[3] = 'Non-program Audio'
XDS_AUDIO_SERVICES_TYPE_SECONDARY[4] = 'Special Effects'

XDS_CAPTION_SERVICES = [
    'field one, channel C1, captioning', 'field one, channel C1, Text',
    'field one, channel C2, captioning', 'field one, channel C2, Text',
    'field two, channel C1, captioning', 'field two, channel C1, Text',
    'field two, channel C2, captioning', 'field two, channel C2, Text',
]

WEATHER_CATEGORY_CODES = {
    'TOA': 'Tornado Watch',                 'TOR': 'Tornado Warning',
    'SVA': 'Severe Thunderstorm Watch',     'SVR': 'Severe Thunderstorm Warning',
    'SVS': 'Severe Weather Statement',      'SPS': 'Special Weather Statement',
    'FFA': 'Flash Flood Watch',             'FFW': 'Flash Flood Warning',
    'FFS': 'Flash Flood Statement',         'FLA': 'Flood Watch',
    'FLW': 'Flood Warning ',                'FLS': 'Flood Statement',
    'WSA': 'Winter Storm Watch',            'WSW': 'Winter Storm Warning',
    'BZW': 'Blizzard Warning',              'HWA': 'High Wind Watch',
    'HWW': 'High Wind Warning',             'HUA': 'Hurricane Watch',
    'HUW': 'Hurricane Warning',             'HLS': 'Hurricane Statement',
    'LFP': 'Service Area Forecast',         'BRT': 'Composite Broadcast Statement',
    'CEM': 'Civil Emergency Message',       'DMO': 'Practice/Demo Warning',
    'ADR': 'Administrative Message'
}

XDS_CGMS = [
    'Copying is permitted without restriction', 'Condition not to be used',
    'One generation of copies may be made',     'No copying is permitted'
]

XDS_CGMS_APS = [  # Macrovision, etc
    'No Analogue protection',                              'Analogue protection: PSP On; Split Burst Off',
    'Analogue protection: PSP On; 2 line Split Burst On',  'Analogue protection: PSP On; 4 line Split Burst On',
]

lastPreambleOffset = 0  # Global cache last preamble offset
lastRowFound = 0  # Global, cache the last row we found cc's on


def memoize(f):
    """ Memoization decorator for performance on inner loop"""

    class Memodict(dict):
        def __getitem__(self, *key):
            return dict.__getitem__(self, key)

        def __missing__(self, key):
            ret = self[key] = f(*key)
            return ret

    return Memodict().__getitem__


class BaseImageWrapper(object):
    def get_pixel_luma(self, x, y):
        """ Return a pixels luma value normalized to the range 0 (black) to 255 (white) """
        raise NotImplemented('get_pixel_luma must be overriden')

    def unlink(self):
        """ Delete the underlying file, and/or release the resource held """
        raise NotImplemented('unlink must be overriden')


class FileImageWrapper(BaseImageWrapper):
    """ A file based wrapper for images """
    def __init__(self, file_name):
        self.image = None
        self.file_name = file_name
        self.height = 0
        self.width = 0

    def unlink(self):
        """ Delete the underlying file, and/or release the resource held """
        self.image = None
        os.unlink(self.file_name)


@memoize
def decode_byte_pair(byte1, byte2):
    """ Decode a pair of bytes"""
    controlcode = (byte1, byte2)
    if controlcode in ALL_CC_CONTROL_CODES:
        return ALL_CC_CONTROL_CODES.get(controlcode)
    if controlcode in ALL_SPECIAL_CHARS:
        return ALL_SPECIAL_CHARS.get(controlcode)
    return '' + CC_TABLE.get(byte1, '????(%02x)' % byte1) + \
           CC_TABLE.get(byte2, '????(%02x)' % byte2)


def decode_byte(image, bit_locations, sample_size, row_number, offset=0):
    """ Decode a single byte from a closed caption images
         bit_locations - where to start sampling for each bit
         sample_size   - how many pixels to average for each bit
         row_number    - which row number to look at
         offset       """
    def pixel_avg(x):
        return sum(image.get_pixel_luma(i + offset, row_number) for i in range(x, x + sample_size)) / sample_size

    b = [pixel_avg(col) > LUMA_THRESHOLD for col in bit_locations]
    return b[0] + b[1] * 2 + b[2] * 4 + b[3] * 8 + b[4] * 16 + b[5] * 32 + b[6] * 64  # TODO parity


def decode_row(image, sample_size=3, row_number=1, offset=0):
    """ Attempt to pull two bytes worth of CC values out of a passed row of luma values
          sample_size - how many pixels wide to read each bit (Noise/drop-out reduction)
          row_number  - which row (y) of video to read as line 21 (typically row 1)
          offset      - column (x) starting offset, default is zero which reflects typical starting point """
    return (decode_byte(image, BYTE1_LOCATIONS, sample_size, row_number, offset),
            decode_byte(image, BYTE2_LOCATIONS, sample_size, row_number, offset))


def is_cc_present(image, row_number=1):
    """ Looks for the sine CC timing signal at the start of a row """
    def pixel(im, x, y):
        return im.get_pixel_luma(x, y)

    def scan_preamble(img, row_num, h_offset, tthreshold):
        for loc in SYNC_SIGNAL_LOCATIONS_HIGH:
            if pixel(img, loc + h_offset, row_num) < tthreshold:
                return False
        for loc in SYNC_SIGNAL_LOCATIONS_LOW:
            if pixel(img, loc + h_offset, row_num) > tthreshold:
                return False
        return True

    global lastPreambleOffset
    if scan_preamble(image, row_number, lastPreambleOffset, LUMA_THRESHOLD):
        return True  # Optimisation - assume preamble doesn't drift

    for offset in PREAMBLE_SCAN_RANGE:
        if scan_preamble(image, row_number, offset, LUMA_THRESHOLD):
            lastPreambleOffset = offset
            ## Found a match - but let's optimize - scan forwards until we break
            for tweak in range(12):
                if not scan_preamble(image, row_number, offset + tweak, LUMA_THRESHOLD):
                    ## Found a negative match, take the middle of the range between the start and end of the match
                    lastPreambleOffset = int(offset + (0.5 * tweak))
                    break
            return True
    return False


def is_control_code(byte1, byte2):
    return (byte1, byte2) in ALL_CC_CONTROL_CODES


def is_end_code(code):
    return 'End of Caption (flip memory)' in code or 'Erase Displayed Memory' in code


def find_and_decode_row(img):
    """ Search for a closed caption row in the passed image, if one is present decode and return the bytes present """
    global lastRowFound
    if not is_cc_present(img, row_number=lastRowFound):
        for row in range(0, img.height+1):
            if is_cc_present(img, row_number=row):
                lastRowFound = row
                return decode_row(img, row_number=lastRowFound)
            return None, None
    else:
        return decode_row(img, row_number=lastRowFound)


def extract_closed_caption_bytes(img):
    """ Returns a tuple of byte values from the passed image object that supports get_pixel_luma """
    byte1, byte2 = find_and_decode_row(img)
    if byte1 is None and byte2 is None:
        return None, False, None, None
    else:
        code = decode_byte_pair(byte1, byte2)
        control = (byte1, byte2) in ALL_CC_CONTROL_CODES
        return code, control, byte1, byte2


def decode_captions_raw(image_list, merge_text=False, delete_image_after=True):
    """ Raw output, show the frame caption codes and frame numbers
         image_list         - list (or generator) of image objects with a get_pixel_luma method
         merge_text         - merge runs of text together and display in a block
         delete_image_after - delete passed images after they've been processed """
    buff = ''  # CC Buffer
    frame = 0
    for image in image_list:
        code, control, _, _ = extract_closed_caption_bytes(image)
        if code is None:
            print('%i skip - no preamble' % frame)
        else:
            if code and not control:
                if merge_text:
                    buff += code
                else:
                    print('%i (%i,%i) - Text:%s' % (frame, lastPreambleOffset, lastRowFound, code))
            elif buff:
                print('%i (%i,%i) - Text:%s' % (frame, lastPreambleOffset, lastRowFound, buff))
                buff = ''
            if control:
                print('%i (%i,%i) - %s' % (frame, lastPreambleOffset, lastRowFound, code))
        frame += 1
        if delete_image_after:
            image.unlink()


def decode_captions_debug(image_list, delete_image_after=True):
    """ Debug output, show the frame caption codes and frame numbers
         image_list         - list (or generator) of image objects with a get_pixel_luma method
         delete_image_after - delete passed images after they've been processed """
    frame = 0
    for image in image_list:
        code, control, b1, b2 = extract_closed_caption_bytes(image)
        if code is None:
            print('%i skip - no preamble' % frame)
        else:
            print('%i (%i,%i) - bytes: 0x%02x 0x%02x : %s' % (frame, lastPreambleOffset, lastRowFound, b1, b2, code))
        frame += 1
        if delete_image_after:
            image.unlink()


def decode_image_list_to_srt(image_list, frames_per_second=29.97, delete_image_after=True):
    """ Decode a passed list of images to a stream of SRT subtitles. Assumes Pop-on format closed captions
         image_list         - list of image file paths
         frames_per_second  - how many fps is the passed list of images
         delete_image_after - delete the image file after we have done processing it"""

    def timestamp(frame_number, fps):
        """Returns an SRT format timestamp"""
        seconds = frame_number / fps
        milliseconds = int((seconds - int(seconds)) * 1000)
        hours = int(seconds / 3600)
        minutes = int((seconds - 3600 * hours) / 60)
        seconds_disp = seconds - (minutes * 60 + hours * 3600)
        return '%02d:%02d:%02d,%03d' % (hours, minutes, seconds_disp, milliseconds)

    def dump_srt_caption(caption_text, start_frame, end_frame, fps):
        """Display an SRT format closed caption"""
        print('%s --> %s\n%s\n' % (timestamp(start_frame, fps), timestamp(end_frame, fps), caption_text))

    offscreen_buffer = ''
    onscreen_buffer = ''
    prevcode = None
    frame = 0
    subtitle_start_frame = 0

    for image in image_list:
        code, control, _, _ = extract_closed_caption_bytes(image)
        if code is not None:
        # PROCESS
            if not control:
                offscreen_buffer += code  # Must be text
            elif control and code != prevcode:
                if 'End of Caption' in code:
                    onscreen_buffer = offscreen_buffer
                    offscreen_buffer = ''
                    subtitle_start_frame = frame
                elif onscreen_buffer and 'Erase Displayed Memory' in code:
                    dump_srt_caption(onscreen_buffer, subtitle_start_frame, frame, frames_per_second)
                    onscreen_buffer = ''
                elif offscreen_buffer and offscreen_buffer[-1:] != '\n':
                    offscreen_buffer += '\n'  # Some random command code. Assume it's just a newline
        # CLEANUP
        prevcode = code
        frame += 1
        if delete_image_after:
            image.unlink()


def decode_captions_to_scc(image_list, delete_image_after=True):
    """ Decode a passed list of images to a stream of SCC subtitles. Assumes Pop-on format closed captions.
        Assumes 29.97 frames per second drop time-code"""

    def drop_frame_time_code(frames):
        frame_number = frames + 18 * (frames / 17982) + 2 * max(((frames % 17982) - 2) / 1798, 0)
        frs = frame_number % 30
        s = (frame_number / 30) % 60
        m = ((frame_number / 30) / 60) % 60
        h = (((frame_number / 30) / 60) / 60) % 24
        return '%02d:%02d:%02d;%02d' % (h, m, s, frs)

    def dump_scc_subtitle(starting_frame, buffer):
        print('%s\t%s' % (drop_frame_time_code(starting_frame), buffer))

    frame = 0
    start_frame = 0
    print('Scenarist_SCC V1.0\n')
    buff = ''
    prevcode = None
    for image in image_list:
        code, control, byte1, byte2 = extract_closed_caption_bytes(image)
        if code is None:
            if code is not None and not buff:
                start_frame = frame  # Start of a sequence (not empty and no buffer yet)
            if code is not None or buff:
                buff += '%x%x ' % (NO_PARITY_TO_ODD_PARITY[byte1], NO_PARITY_TO_ODD_PARITY[byte2])
            if control and is_end_code(code) and code == prevcode:
                dump_scc_subtitle(start_frame, buff)
                buff = ''
        frame += 1
        prevcode = code
        if delete_image_after:
            image.unlink()


def compute_xds_packet_checksum(packet_bytes):
    """ Return the true if the xds packet checksum is okay """
    def twos_complement(bitvalue):
        """ Return the passed value translated to a 7 bit two's completement value """
        return 128 - bitvalue if (bitvalue & 0x7f) != 0 else bitvalue

    if packet_bytes:  # Whole packet should sum to zero in two's complement
        return not(sum(twos_complement(b1) + twos_complement(b2) for (b1, b2) in packet_bytes) & 0x07f)
    return False


def _assert_len(xds_inputbytes, minimum):
    """ Asserts that there are least minimum bytes in the passed xds input bytes buffer """
    if len(xds_inputbytes) * 2 < minimum:
        raise RuntimeWarning('Malformed packet')


def decode_xds_string(pbytes):
    """ Return a string from a series of packet bytes """
    xds_string = ''
    while pbytes:
        strbyte1, strbyte2 = pbytes.pop(0)
        if strbyte1 == 0x0f:
            break
        xds_string += decode_byte_pair(strbyte1, strbyte2)
    return xds_string


def decode_xds_minutes_hours(pbytes, short=False):
    """ Pull minutes, then hours from a packet """
    _assert_len(pbytes, 2)
    minb, hourb = pbytes.pop(0)
    return minb & 63, hourb & 31 if short else hourb & 63


def decode_xds_content_advisory(pbytes):
    """ Decode content advisory packet, returning a string describing the rating """
    _assert_len(pbytes, 2)
    ca1, ca2 = pbytes.pop(0)
    system = ca1 & 24 >> 3
    rating = ''
    if system == 0 or system == 2:  # MPA
        rating = MPA_RATING[ca1 & 7]
    elif system == 1:  # US TV Parent Guidelines
        rating_code = ca1 & 7
        rating = US_TV_PARENTAL_GUIDELINE_RATING[rating_code]
        if rating_code == 2:
            rating += ' Fantasy Violence' if ca2 & 32 else ''
        elif 4 <= rating_code <= 6:
            rating += ' Violence' if ca2 & 32 else ''
            rating += ' Sexual Situations' if ca2 & 16 else ''
            rating += ' Adult Language' if ca2 & 8 else ''
            rating += ' Sexually Suggestive Dialogue' if ca1 & 32 else ''
    elif system == 3:  # International
        subsystem = (ca1 & 32 >> 5) + (ca2 & 8 >> 2)
        if subsystem == 1:  # CAD English
            rating = CANADIAN_ENGLISH_RATINGS[ca2 & 7]
        elif subsystem == 2:
            rating = CANADIAN_FRENCH_RATINGS[ca2 & 7]
        else:  # Reserved for some international system
            rating = 'International reserved code %s' % str((ca1, ca2))
    return 'XDS Rating: %s' % rating


def describe_xds_packet(packet_bytes):
    """ Given a set of bytes representing an XDS packet, describe it """
    if packet_bytes:
        if not compute_xds_packet_checksum(packet_bytes):
            return 'XDS Rejected Packet - Incorrect Checksum'
        b1, b2 = packet_bytes.pop(0)
        if b1 <= 0x02 and b2 <= 0x03:  # TODO continues
            pref = ['Current', 'Next Program'][b1-1]
            if b2 == 0x01:  # Program identification number
                _assert_len(packet_bytes, 4)
                minutes, hours = decode_xds_minutes_hours(packet_bytes, short=True)
                dateb, monthb = packet_bytes.pop(0)
                tape_delay = '(Tape Delayed)' if (monthb & 16) else ''
                return ('XDS %s Scheduled Start Time: %02i:%02i on Day %02i of Month %02i %s'
                        % (pref, hours, minutes, dateb & 31, monthb & 15, tape_delay))
            elif b2 == 0x02:  # Length and elapsed
                _assert_len(packet_bytes, 2)
                minutes, hours = decode_xds_minutes_hours(packet_bytes)
                msg = 'XDS %s Length of Show: %02i:%02i' % (pref, hours, minutes)
                if packet_bytes:
                    minutes, hours = decode_xds_minutes_hours(packet_bytes)
                    seconds = 0
                    if packet_bytes:
                        seconds = packet_bytes.pop(0)[0] & 63
                    msg += ' XDS %s Elapsed time: %02i:%02i:%02i' % (pref, hours, minutes, seconds)
                return msg
            elif b2 == 0x03:  # Program Name
                return 'XDS %s Program Name: %s' % (pref, decode_xds_string(packet_bytes))
        if b1 == 0x01:
            if b2 == 0x04:  # Program Type
                program_genre = ''
                while packet_bytes:
                    n1, n2 = packet_bytes.pop(0)
                    if n1 == 0x0f:
                        break
                    program_genre += '%s %s ' % (XDS_GENRE_CODES.get(n1, ''), XDS_GENRE_CODES.get(n2, ''))
                return 'XDS Program Genre: %s' % program_genre
            elif b2 == 0x05:  # Content advisory - Vchip !
                return decode_xds_content_advisory(packet_bytes)
            elif b2 == 0x06:  # Audio services
                main, sap = packet_bytes.pop(0)
                main_language = XDS_AUDIO_SERVICES_LANGUAGE[main & 56 >> 3]
                main_type = XDS_AUDIO_SERVICES_TYPE_MAIN[main & 7]
                sap_language = XDS_AUDIO_SERVICES_LANGUAGE[sap & 56 >> 3]
                sap_type = XDS_AUDIO_SERVICES_TYPE_SECONDARY[sap & 7]
                return 'XDS Audio Services: Main:%s(%s) Sap:%s(%s)' % (main_language, main_type, sap_language, sap_type)
            elif b2 == 0x07:  # Caption services
                return 'XDS Caption Services'  # TODO
            elif b2 == 0x08:  # CGMS
                _assert_len(packet_bytes, 2)
                c1, _ = packet_bytes.pop(0)
                copying = XDS_CGMS[c1 & 24 >> 3]
                protection = XDS_CGMS_APS[c1 & 7]
                return 'XDS Copy protection: %s %s' % (copying, protection)
            elif b2 == 0x09:  # Aspect ratio
                _assert_len(packet_bytes, 2)
                startl, endl = packet_bytes.pop(0)
                anamorp = False
                if packet_bytes:
                    anamorp, _ = packet_bytes.pop(0)
                return 'XDS Aspect Ratio: start line: %i end line: %i %s' \
                       % (22 + (startl & 63), 262 - (endl & 63), (anamorp & 1) and 'Anamorphic')
            elif b2 == 0x0c:  # Composite packet
                return 'Composite packet 1'  # TODO - pending confirmation of the spec
            elif b2 == 0x0d:
                return 'Composite packet 2'  # TODO
            elif 0x10 <= b2 <= 0x17:  # Program description
                return 'XDS Program description line: %i :%s ' % ((b2 - 0x0F), decode_xds_string(packet_bytes))

        if b1 == 0x05:  # Channel Information class
            if b2 == 0x01:  # Channel name
                return 'XDS Channel Name: %s' % decode_xds_string(packet_bytes)
            if b2 == 0x02:  # Station call-sign
                return 'XDS Channel Station Call-Sign: %s' % decode_xds_string(packet_bytes)
            if b2 == 0x03:  # Tape delay
                minutes, hours = decode_xds_minutes_hours(packet_bytes, short=True)
                return 'XDS Channel Tape Delay: %02i:%02i' % (hours, minutes)
        if b1 == 0x09:  # Public service
            if b2 == 0x01:  # Weather advisory WRSAME format
                return 'XDS Public Service - WRSAME message: %s' % str(packet_bytes)  # TODO, the spec is a bit vague
            if b2 == 0x02:  # Weather message
                return 'XDS Public Service - Weather: %s' % decode_xds_string(packet_bytes)

        return 'Could not decode ---> XDS describes: %02x %02x' % (b1, b2)
    return 'XDS - Empty Packet'


def decode_xds_packets(image_list, delete_image_after=True):
    """ Decode a passed list of images to a stream of XDS packets. """
    frame = 0
    packetbuf = []
    gather_xds_bytes = False
    for image in image_list:
        frame += 1
        code, control, b1, b2 = extract_closed_caption_bytes(image)
        if code is not None:
            if not (b1 == 0 and b2 == 0):  # Stuffing, ignore and continue
                if b1 <= 0x0e:  # Start of XDS packet'
                    gather_xds_bytes = True
                if gather_xds_bytes:
                    packetbuf.append((b1, b2))
                if b1 == 0x0f:  # End of XDS packet
                    gather_xds_bytes = False
                    print(describe_xds_packet(packetbuf))
                    packetbuf = []
        if delete_image_after:
            image.unlink()
