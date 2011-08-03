import zmstream
import cv
import math
import pprint
import os
import sys
import tempfile

class Percept :
	def image_jpegstr(self, jpeg_str) :
		# this isn't great but OpenCV's a bit of a jerk about loading images
		fn = tempfile.mktemp('.jpg')
		try :
			h = open(fn, 'w')
			h.write(jpeg_str)
			h.close()

			return cv.LoadImage(fn)
		finally :
			os.unlink(fn)

	def filter_edges(self, img) :
		sz = cv.GetSize(img)
		bw = cv.CreateMat(sz[1], sz[0], cv.CV_8U)
		med = cv.CreateMat(sz[1], sz[0], cv.CV_8U)
		canny = cv.CreateMat(sz[1], sz[0], cv.CV_8U)
		cv.CvtColor(img, bw, cv.CV_RGB2GRAY)
		cv.Smooth(bw, med, cv.CV_MEDIAN, 5)
		cv.Canny(med, canny, 75, 112, 3)
		return canny

	def dict_diff(self, d1, d2) :
		key_merge = set(d1.keys()).intersection(d2.keys())
		result = {}
		for k in key_merge :
			result[k] = abs(d1[k] - d2[k])
		return result
	
	def bin_edgecount(self, img, bins=24) :
		sz = cv.GetSize(img)
		twi = sz[0]
		thi = sz[1]
		tw = float(twi)
		th = float(thi)
		ta = tw * th
		r = tw/th
		a = ta / bins
		h = int(math.pow(a / r, 0.5))
		w = int(a / h)

		# bin maximums, integer rounded
		wbm = twi / w
		hbm = thi / h
		whitecounts = {}
		for wb in range(wbm) :
			for hb in range (hbm) :
				whitecounts[wb, hb] = 0

		for wo in range(wbm * w) :
			for ho in range(hbm * h) :
				# integer division for the counts, find bin numbers for current pixel
				b_w = wo / w
				b_h = ho / h
				v = img[ho, wo]
				if v > 0 :
					whitecounts[b_w, b_h] += 1

		return whitecounts

if __name__ == '__main__' :
	p = Percept()
	url = sys.argv[1]
	streamer = zmstream.ZMStreamer(1, url)
	edge_bin = {}
	for i in streamer.generate() :
		img = p.image_jpegstr(i)
		filtered = p.filter_edges(img)

		cv.SaveImage('edges.png', filtered)

		new_bin = p.bin_edgecount(filtered)
		diff = p.dict_diff(new_bin, edge_bin)
		edge_bin = new_bin

		for k in diff :
			diff[k] = '=' * (diff[k] / 5)

		pprint.pprint(diff)
