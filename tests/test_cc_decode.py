from unittest import TestCase
from lib.cc_decode import decode_byte_pair, decode_byte, BYTE1_LOCATIONS, find_and_decode_row, \
    compute_xds_packet_checksum, extract_closed_caption_bytes, _assert_len, decode_xds_string, decode_xds_minutes_hours, \
    describe_xds_packet, decode_captions_debug, decode_image_list_to_srt, decode_captions_to_scc, decode_xds_packets, \
    decode_captions_raw, decode_row, decode_xds_content_advisory, BYTE2_LOCATIONS, SYNC_SIGNAL_LOCATIONS_HIGH, \
    ALL_SPECIAL_CHARS, CC_TABLE
from random import randint

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


class MockImage(object):
    def __init__(self, val, h=480, w=720):
        self.val = val
        self.height = h
        self.width = w

    def get_pixel_luma(self, x, y):
        return self.val

    def unlink(self):
        pass


class RandomMockImage(MockImage):
    def get_pixel_luma(self, x, y):
        return randint(0,255)


class MockImageWithBytes(MockImage):
    def __init__(self, val1, val2, h=480, w=720):
        super().__init__(None)
        self.val1 = val1
        self.val2 = val2
        self.height = h
        self.width = w

    def get_pixel_luma(self, x, y):
        def in_range(x, loc_list, val=0, force_high=False):
            for i, pixel_loc in enumerate(loc_list):
                if pixel_loc - 5 < x < pixel_loc + 5:
                    if val & (2 ** i) or force_high:
                        return 100
            return 0
        if x >= self.width or y >= self.height:
            raise IndexError('Pixel outside expected range')

        return in_range(x, SYNC_SIGNAL_LOCATIONS_HIGH, force_high=True) or \
                in_range(x, BYTE1_LOCATIONS, val=self.val1) or \
                in_range(x, BYTE2_LOCATIONS, val=self.val2) or 0


MOCK_IMAGE_SEQUENCE = ([MockImage(0, h=1)] * 100) + ([MockImage(0, h=5)] * 100)
RANDOM_MOCK_IMAGE_SEQUENCE = ([RandomMockImage(0, h=1)] * 1000) + \
                             ([RandomMockImage(0, h=5)] * 1000) + \
                             ([RandomMockImage(0, h=2)] * 1000)

class TestDecoding(TestCase):
    def create_image_sequence(self, values, image_height=1):
        img_seq = []
        for val1, val2 in values:
            img_seq.append(MockImageWithBytes(val1, val2, h=image_height))
        return img_seq

    def exercise_decoder(self, decoder_method, values):
        img_seq = self.create_image_sequence(values)
        retval = decoder_method(img_seq)
        if retval is not None:
            self.assertEqual(retval, values)

    def generate_sequences(self):
        testcases = []

        # All the special characters
        testcase = [[0x14, 0x20]]
        for sc in ALL_SPECIAL_CHARS:
            testcase.append(list(sc))
        testcase.append([0x14, 0x20])
        testcases.append(testcase)

        # All the basic characters
        testcase = [[0x14, 0x20]]
        for ch in CC_TABLE:
            testcase.append([ch, ch])
        testcase.append([0x14, 0x20])
        testcases.append(testcase)
        return testcases

    def xds_test_case(self):
        return [[0x15, 0x2c], [0x05, 0x02], [0x43, 0x43], [0x54, 0x56], [0x0f, 0x3a], [0x01, 0x02],
                [0x5d, 0x40], [0x40, 0x40], [0x0f, 0x51], [0x01, 0x03], [0x44, 0x75], [0x63, 0x6b],
                [0x6d, 0x61], [0x01, 0x05], [0x48, 0x44], [0x0f, 0x5f], [0x02, 0x03], [0x6e, 0x00],
                [0x0f, 0x2a], [0x05, 0x01], [0x43, 0x6f], [0x6d, 0x65], [0x64, 0x79], [0x20, 0x43],
                [0x65, 0x6e], [0x74, 0x72], [0x61, 0x6c], [0x0f, 0x21], [0x01, 0x01], [0x40, 0x48],
                [0x57, 0x45], [0x0f, 0x4b]]

    def test_exercise_decoders(self):
        decoder_methods = [decode_captions_debug, decode_image_list_to_srt, decode_captions_to_scc, decode_xds_packets,
                           decode_captions_raw]

        test_image_values = [[[0x20, 0x20], [0x20, 0x20], [0x20, 0x20]]]
        test_image_values.extend(self.generate_sequences())
        test_image_values.append(self.xds_test_case())
        for test_case in test_image_values:
            for decoder_method in decoder_methods:
                self.exercise_decoder(decoder_method, test_case)

    def test_decode_byte_pair(self):
        testcases = [
            ((0, 0),       ''),
            ((0xFF, 0xFF), '????(ff)????(ff)'),
            ((0x14, 0x20), 'CC1 Resume Caption Loading'),
            ((0x20, 0x20), '  '),
            ((0x19, 0x27), 'CC2 Mid-row: Cyan Underline'),
            ((0x24, 0x24), '$$'),
        ]
        for test in testcases:
            self.assertEqual(decode_byte_pair(*test[0]), test[1])

    def test_decode_byte(self):
        self.assertEquals(decode_byte(MockImage(100), BYTE1_LOCATIONS, 5, 1, 1), 127)
        self.assertEquals(decode_byte(MockImage(0),   BYTE1_LOCATIONS, 5, 1, 1), 0)
        self.assertEquals(decode_byte(MockImage(0),   BYTE1_LOCATIONS, 50, 10, 10), 0)
        self.assertEquals(decode_byte(MockImage(100), BYTE1_LOCATIONS, 50, 10, 10), 127)

    def test_decode_row(self):
        self.assertEquals(decode_row(MockImage(100)), (127, 127))

    def test_find_and_decode(self):
        self.assertEquals(find_and_decode_row(MockImage(0)), (None, None))
        self.assertEquals(find_and_decode_row(MockImage(100)), (None, None))

    def test_extract_closed_caption_bytes(self):
        self.assertEquals(extract_closed_caption_bytes(MockImage(0)), (None, False, None, None))
        self.assertEquals(extract_closed_caption_bytes(MockImage(100)), (None, False, None, None))

    def test_compute_xds_packet_checksum(self):
        self.assertEquals(compute_xds_packet_checksum([]), False)
        self.assertEquals(compute_xds_packet_checksum([(0, 0)]), True)

    def test_assert_len(self):
        self.assertEquals(_assert_len([(0, 0), (0, 0)], 4), None)
        self.assertRaises(RuntimeWarning, _assert_len, [(0, 0), (0, 0)], 10)

    def test_decode_xds_string(self):
        self.assertEquals(decode_xds_string([[ord('A'), ord('B')], [ord('C'), ord('D')], [0x0F, 0x00]]), 'ABCD')
        self.assertEquals(decode_xds_string([]), '')
        self.assertEquals(decode_xds_string([[0x0F, 0x00]]), '')

    def test_decode_xds_minutes_hours(self):
        self.assertEquals(decode_xds_minutes_hours([[5 | 128, 5 | 128]]), (5, 5))

    def test_describe_xds_packet(self):
        self.assertEquals(describe_xds_packet([]), 'XDS - Empty Packet')

    def test_decode_xds_packets(self):
        decode_xds_packets(MOCK_IMAGE_SEQUENCE)
        decode_xds_packets(RANDOM_MOCK_IMAGE_SEQUENCE)

    def test_decode_scc(self):
        decode_captions_to_scc(MOCK_IMAGE_SEQUENCE)
        decode_captions_to_scc(RANDOM_MOCK_IMAGE_SEQUENCE)

    def test_decode_raw(self):
        decode_image_list_to_srt(MOCK_IMAGE_SEQUENCE)
        decode_image_list_to_srt(RANDOM_MOCK_IMAGE_SEQUENCE)

    def test_decode_captions_debug(self):
        decode_captions_debug(MOCK_IMAGE_SEQUENCE)
        decode_captions_debug(RANDOM_MOCK_IMAGE_SEQUENCE)

    def test_decode_captions_raw(self):
        decode_captions_raw(MOCK_IMAGE_SEQUENCE)
        decode_captions_raw(RANDOM_MOCK_IMAGE_SEQUENCE)

    def test_decode_xds_content_advisory(self):
        decode_xds_content_advisory([[0x05, 0x05]])