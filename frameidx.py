"""

Module for storing (and later to be developed, retrieving with intelligent filters) frames that are of interest.

Caveats: assumes no more than one frame per second - could go to milliseconds later

"""

import bitarray
import os.path
import os, errno
import struct

def mkdir_p(path):
	try:
		os.makedirs(path)
	except OSError as exc:
		if exc.errno == errno.EEXIST and os.path.isdir(path):
			pass
		else:
			raise

# this isn't for display, if you open a ticket about this I'll be like ;p
DIR_CHUNKING = 86400

class IDX(object) :
	"""
	Record jpeg frames with metadata in a small index. NOT THREAD SAFE.
	"""

	def __init__(self, name, directory='var/frames') :
		self.name = name
		self.directory = directory
		
		self.directory_known_cache = set()
		
		self.index_write_handle = None

	#### FILE/DIRECTORY MANIPULATION ####

	def mkdirp(self, path) :
		if path not in self.directory_known_cache :
			mkdir_p(path)
			self.directory_known_cache.add(path)

	def fn_namer(self, filename, subdir=None) :
		path = os.path.join(self.directory, self.name)
		if subdir is not None :
			path = os.path.join(path, subdir)
		self.mkdirp(path)
		return os.path.join(path, filename)

	def fn_opener(self, filename, mode, subdir=None) :
		return open(self.fn_namer(filename, subdir=subdir), mode)

	def get_subdir(self, ts) :
		return '%d' % (ts // DIR_CHUNKING)

	def index_namer(self, ts) :
		return self.fn_namer('frames.idx', subdir=self.get_subdir(ts))

	def jpeg_opener(self, ts, mode='r') :
		return self.fn_opener('%d.jpg' % ts, mode, subdir=self.get_subdir(ts))

	#### INDEXING ####

	def add_file(self, ts, jpeg_str, busy_percentage, busy_bitfield) :
		# first record file, don't add to index unless that's worked out.
		jfh = self.jpeg_opener(ts, mode='w')
		try :
			jfh.write(jpeg_str)
		finally :
			jfh.close()

		# make sure we have the right index open
		index_name = self.index_namer(ts)
		if self.index_write_handle is None :
			self.index_write_handle = open(index_name, 'w')
		elif self.index_write_handle.name != index_name :
			self.index_write_handle.close()
			self.index_write_handle = open(index_name, 'w')

		# now calculate each of the things that needs calculating and create a buffer

		## calculate busy_bitfield_size
		busy_bitfield_size = len(busy_bitfield)

		## calculate busyf
		busyf = 0
		for i in range(busy_bitfield_size) :
			if busy_bitfield[i] :
				busyf += 1

		# index block
		# magic ascii to make hex editing not insane.
		buf = 'FIDX' + struct.pack('!qbhh', ts, busy_percentage, busyf, busy_bitfield_size) + busy_bitfield.tobytes()
		
		# now write to the index
		# TODO prevent partial write somehow. Magical transactional filesystem moves?
		self.index_write_handle.write(buf)

		# flush it!
		self.index_write_handle.flush()
