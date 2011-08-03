import zmstream
import cv
import os
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

if __name__ == '__main__' :
	import sys

	p = Percept()
	url = sys.argv[1]
	streamer = zmstream.ZMStreamer(1, url)
	for i in streamer.generate() :
		img = p.image_jpegstr(i)
		filtered = p.filter_edges(img)
		cv.SaveImage('edges.png', filtered)
		sys.exit(1)
