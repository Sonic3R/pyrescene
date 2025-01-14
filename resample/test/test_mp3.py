#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 pyReScene
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

import io
import os
import struct
import unittest

from resample import mp3

class TestId3v2SizeField(unittest.TestCase):
	"""Testing helper functions for ID3v2 tag size field."""
	def test_encode(self):
		start = 128
		result = mp3.encode_id3_size(start)
		self.assertEqual(b"\x00\x00\x01\x00", result)
		start = 0x80 + 0x11  # 128 + more bits
		result = mp3.encode_id3_size(start)
		self.assertEqual(b"\x00\x00\x01\x11", result)
		size = b"\x00\x00\x02\x23"
		start = mp3.decode_id3_size(size)
		result = mp3.encode_id3_size(start)
		self.assertEqual(size, result)
		result = mp3.encode_id3_size(150584481)
		self.assertEqual(b"\x47\x66\x79\x21", result)
		result = mp3.encode_id3_size(9999999999)
		self.assertTrue(len(result) == 4)
		self.assertEqual(b" /G\x7f", result)
		self.assertNotEqual(9999999999, mp3.decode_id3_size(b" /G\x7f"))

	def test_decode(self):
		start = 1337
		result = mp3.decode_id3_size(mp3.encode_id3_size(start))
		self.assertEqual(start, result)

class TestDoubleId3v2(unittest.TestCase):
	"""Test for bad data in (angelmoon)-hes_all_i_want_cd_pg2k-bmi
	VLC and mpc-hc can only play it after removing the crap of first ID3 tag 
	fpcalc fails on it too, but succeeds when bad tag is removed."""

	def setUp(self):
		self.mp3stream = io.BytesIO()

		# bad ID3 tag (10 bytes)
		self.mp3stream.write(b"ID3")
		self.mp3stream.write(b"N" * 7)  # nfo data or other crap in file

		# good ID3 tag (20 bytes)
		writeId3v2Tag(self.mp3stream, 20)

	def test_parse_bad_good(self):
		# mp3 stuff (10 bytes)
		writeMp3Data(self.mp3stream, 10)

		# test if parsing succeeds
		mr = mp3.Mp3Reader(stream=self.mp3stream)
		generator = mr.read()
		id3 = next(generator)
		self.assertEqual(0, id3.start_pos)
		crap_size_value = mp3.decode_id3_size(b"NNNN")  # + 10B ID3 header
		self.assertEqual(crap_size_value + 10, id3.size)

		good_id3 = next(generator)
		self.assertEqual(10, good_id3.start_pos)
		self.assertEqual(20, good_id3.size)

		mp3data = next(generator)
		self.assertEqual(30, mp3data.start_pos)
		self.assertEqual(10, mp3data.size)
		self.assertRaises(StopIteration, next, generator)

	def test_last_id3v2_before_sync(self):
		"""Looks like you will get an infinite loop if the first FF byte 
		is not FFE0; perhaps the next find should start at c + 1?"""
		self.mp3stream.write(b"\xFF\x11\x22\x33\x44")
		self.mp3stream.write(b"\xFF\xE0")
		offset = mp3.last_id3v2_before_sync(self.mp3stream, 37)
		self.assertEqual(10, offset)

	def test_last_id3v2_before_sync_one(self):
		"""\xFF\xFF will match."""
		self.mp3stream.write(b"\xFF\xFF\xE0\x33\x44")
		offset = mp3.last_id3v2_before_sync(self.mp3stream, 35)
		self.assertEqual(10, offset)

	def test_last_id3v2_before_sync_two(self):
		"""First FF match fails, but still find the following sync bytes."""
		self.mp3stream.write(b"\xFF\x00\xFF\xE0\x44")
		offset = mp3.last_id3v2_before_sync(self.mp3stream, 35)
		self.assertEqual(10, offset)

	def test_last_id3v2_before_sync_border_case(self):
		"""I think if find returns c = 0x10002 the BE_SHORT.unpack will only 
		get one byte, so maybe the find calls should be limited to 0x10002?"""
		self.mp3stream.write(b"\x00" * (0x10002 - 30))
		self.mp3stream.write(b"\xFF")
		offset = mp3.last_id3v2_before_sync(self.mp3stream, 0x10003)
		self.assertEqual(0, offset)

		# remember last ID3 tag between loops
		self.mp3stream.seek(0, os.SEEK_END)
		self.mp3stream.write(b"\xE0")
		offset = mp3.last_id3v2_before_sync(self.mp3stream, 0x10004)
		self.assertEqual(10, offset)
		
	def test_parse_double_good(self):
		"""Check if parsing works for two good ID3v2 tags in the SRS file.
		POP_ETC-POP_ETC-2012-CaHeSo/09-pop_etc-i_wanna_be_your_man.mp3"""
		stream = io.BytesIO()
		writeId3v2Tag(stream, 42)
		writeId3v2Tag(stream, 42)
		writeSrsFileTag(stream, 11)
		writeId3v1Tag(stream)
		
		# test if parsing succeeds
		mr = mp3.Mp3Reader(stream=stream)
		generator = mr.read()

		id3one = next(generator)
		self.assertEqual(0, id3one.start_pos)
		self.assertEqual(42, id3one.size)

		id3two = next(generator)
		self.assertEqual(42, id3two.start_pos)
		self.assertEqual(42, id3two.size)

		srstrack = next(generator)
		self.assertEqual(42 + 42, srstrack.start_pos)
		self.assertEqual(11, srstrack.size)

		next(generator)

		self.assertRaises(StopIteration, next, generator)

	def test_parse_double_good_bad_good(self):
		stream = io.BytesIO()
		writeId3v2Tag(stream, 42)
		stream.write(b"CRAPCRAP")
		writeId3v2Tag(stream, 42)
		writeSrsFileTag(stream, 11)
		writeId3v1Tag(stream)
		
		# test if parsing succeeds
		mr = mp3.Mp3Reader(stream=stream)
		generator = mr.read()

		# crap and second tag get counted with the first one
		id3one = next(generator)
		self.assertEqual(0, id3one.start_pos)
		self.assertEqual(42 + 8 + 42, id3one.size)

		srstrack = next(generator)
		self.assertEqual(42 + 8 + 42, srstrack.start_pos)
		self.assertEqual(11, srstrack.size)

		next(generator)

		self.assertRaises(StopIteration, next, generator)

	def test_parse_loop_id3v2_srs(self):
		stream = io.BytesIO()
		writeId3v2Tag(stream, 20)
		writeId3v2Tag(stream, 20)
		writeId3v2Tag(stream, 20)
		writeSrsFileTag(stream, 20)
		
		# test if parsing succeeds
		mr = mp3.Mp3Reader(stream=stream)
		generator = mr.read()

		id3one = next(generator)
		self.assertEqual(0, id3one.start_pos)
		self.assertEqual(20, id3one.size)

		next(generator)
		next(generator)

		srstrack = next(generator)
		self.assertEqual(60, srstrack.start_pos)
		self.assertEqual(20, srstrack.size)

		self.assertRaises(StopIteration, next, generator)

	def test_parse_loop_id3v2_bad_mp3(self):
		stream = io.BytesIO()
		writeId3v2Tag(stream, 20)
		writeId3v2Tag(stream, 20)
		writeId3v2Tag(stream, 20)
		
		# 1 bad byte + 4 bytes mp3 data
		stream.write(b"\x11\xFF\xE0\x33\x44")
		
		# test if parsing succeeds
		mr = mp3.Mp3Reader(stream=stream)
		generator = mr.read()

		id3one = next(generator)
		self.assertEqual(0, id3one.start_pos)
		self.assertEqual(20, id3one.size)

		next(generator)

		id3three = next(generator)
		self.assertEqual(40, id3three.start_pos)
		self.assertEqual(20, id3three.size)

		# bad data between last good id3 and mp3 is counted with mp3 data
		# this is because there can be a lot of crap following the tags
		mp3track = next(generator)
		self.assertEqual(60, mp3track.start_pos)
		self.assertEqual(5, mp3track.size)

		self.assertRaises(StopIteration, next, generator)

class TestDoubleEndTags(unittest.TestCase):
	"""MP3 files can become too large and the end data is repeated.
	FTP ASCII/BIN transfer mix + file resume can result to this"""

	def test_parse(self):
		mp3stream = io.BytesIO()

		# good ID3 tag (20 bytes)
		writeId3v2Tag(mp3stream, 20)

		# mp3 stuff (30 bytes)
		writeMp3Data(mp3stream, 30)

		# repeating tags (with bad data inbetween) are a problem for retagging
		writeId3v1Tag(mp3stream)
		mp3stream.write(b"B" * 10)  # not necessary for test
		writeId3v1Tag(mp3stream)

		# test if parsing succeeds
		mr = mp3.Mp3Reader(stream=mp3stream)
		generator = mr.read()
		id3v2 = next(generator)
		self.assertEqual(0, id3v2.start_pos)
		self.assertEqual(20, id3v2.size)

		mp3data = next(generator)
		self.assertEqual(20, mp3data.start_pos)
		mp3_size = 30 + 128 + 10
		self.assertEqual(mp3_size, mp3data.size)
		# the crap is included in the mp3 data block
		# it'll have to be cut off when retagging

		id3v1 = next(generator)
		self.assertEqual(20 + mp3_size, id3v1.start_pos)
		self.assertEqual(128, id3v1.size)

		self.assertRaises(StopIteration, next, generator)

class TestTags(unittest.TestCase):
	def test_small_mp3(self):
		mp3stream = io.BytesIO()
		writeMp3Data(mp3stream, 2)
		mp3.Mp3Reader(stream=mp3stream)
		# no crash: technically there are 2 bytes of 'mp3' data

	def test_id3v2_only(self):
		mp3stream = io.BytesIO()
		writeId3v2Tag(mp3stream, 123)
		self.assertRaises(mp3.InvalidDataException,
		                  mp3.Mp3Reader, stream=mp3stream)

	def test_id3(self):
		mp3stream = io.BytesIO()
		id3v2size = 10
		writeId3v2Tag(mp3stream, id3v2size)
		writeMp3Data(mp3stream, 2)
		writeId3v1Tag(mp3stream)

		# test if parsing succeeds
		mr = mp3.Mp3Reader(stream=mp3stream)
		generator = mr.read()
		id3 = next(generator)
		self.assertEqual(0, id3.start_pos)
		self.assertEqual(id3v2size, id3.size)

		mp3data = next(generator)
		self.assertEqual(id3v2size, mp3data.start_pos)
		self.assertEqual(2, mp3data.size)

		id3v1 = next(generator)
		self.assertEqual(id3v2size + 2, id3v1.start_pos)
		self.assertEqual(128, id3v1.size)

def writeId3v2Tag(stream, size=20):
	assert size >= 10, "ID3v2 block must have a 10 byte header"
	stream.write(b"ID3")
	stream.write(b"\x03\x00\x00")  # version info and flags
	stream.write(mp3.encode_id3_size(size - 10))  # 10 byte header not included
	stream.write(b"2" * (size - 10))  # data

def writeMp3Data(stream, size=20):
	assert size >= 2, "The sync bytes require 2 bytes"
	stream.write(b"\xFF\xE7")  # mp3 frame marker (11 bits)
	stream.write(b"M" * (size - 2))

def writeId3v1Tag(stream):
	stream.write(b"TAG")
	stream.write(b"1" * (128 - 3))

def writeSrsFileTag(stream, size=20):
	assert size >= 8, "8 byte header minimum"
	stream.write(b"SRSF")
	stream.write(struct.pack("<L", size))
	stream.write(b"S" * (size - 8))

if __name__ == "__main__":
	unittest.main()
