#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

try:
	import _preamble
except ImportError:
	pass

from resample.srs import main
main(sys.argv[1:])