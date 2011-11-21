import zmstream
import cv
import math
import pprint
import os
import sys
import tempfile
import threading
import time
import json
import Queue

SOCKET_RETRY_SEC = 10
NO_FRAME_THR = 10
BUSY_SEC = 120
SEC_BEFORE_UNK = 20
FPS = 1
#FIXME if BUSY_THR goes over the max number for the last-motion buffer, ratio will be 1.0 all the time
BUSY_THR = FPS * BUSY_SEC

class Percept(threading.Thread) :
	def __init__(self, camname, url, auth=None, zm_auth_hash_secret=None, zmq_url=None, mode=zmstream.Mode.MJPEG) :
		self.camname = camname
		self.url = url
		self.auth = auth
		self.zm_auth_hash_secret = zm_auth_hash_secret
		self.zmq_url = zmq_url
		self.mode = mode
		self.ok = True
		self.active = True
		self.frame_time = None
		self.ratio_busy = None
		self.alerts = []
		threading.Thread.__init__(self)

	def image_pil(self, pil_image) :
		cv_im = cv.CreateImageHeader(pil_image.size, cv.IPL_DEPTH_8U, 3)
		cv.SetData(cv_im, pil_image.tostring())
		return cv_im

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
	
	def bin_edgecount(self, img, bins=4096) :
		sz = cv.GetSize(img)
		twi = sz[1]
		thi = sz[0]
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
				v = img[wo, ho]
				if v > 0 :
					whitecounts[b_w, b_h] += 1

		return whitecounts

	def get_size_for_bin_images(self, bindict) :
		width = max([x for x,y in bindict.keys()]) + 1
		bins = len(bindict)
		height = bins / width
		return width, height

	def bins_to_img(self, bindict) :
		if not bindict :
			return None
		
		width, height = self.get_size_for_bin_images(bindict)

		img = cv.CreateMat(width, height, cv.CV_8U)
		# hardcode scaling
		scaling = 10
		# auto scaling
		#scaling = 255 / float(max(bindict.values()))

		#print "wb %d hb %d sc %0.3f" % (width, height, scaling)

		for x,y in bindict :
			try :
				# scaled from maximum
				img[x,y] = min(255, int(scaling * float(bindict[x,y])))
				# clipped, shown direct difference
				#img[x,y] = min(255, bindict[x,y])
			except ZeroDivisionError :
				img[x,y] = 0
		return img

	def get_wh(self, img) :
		height, width = cv.GetSize(img)
		return width, height

	def create_image_matching_size(self, img, depth) :
		width, height = self.get_wh(img)
		img_out = cv.CreateMat(width, height, depth)
		return width, height, img_out

	def filter_for_blobs(self, img) :
		width, height, img_out = self.create_image_matching_size(img, cv.CV_8U)

		THRESHOLD = 80
		RATIO = .3
		KS = 5

		border = (KS - 1) / 2

		for x in range(0, width) :
			for y in range(0, height) :
				if x < border or x >= width - border or y < border or y >= height - border :
					img_out[x,y] = 0
				else :
					c = 0
					for xc in range(-border, border+1) :
						for yc in range(-border, border+1) :
							if img[xc+x, yc+y] >= THRESHOLD :
								c += 1
					if c >= RATIO * KS * KS :
						img_out[x,y] = 255
					else :
						img_out[x,y] = 0

		return img_out

	def frames_ago(self, motionframe, history) :
		MAX = 256 - 1

		if history is None :
			width, height, history = self.create_image_matching_size(motionframe, cv.CV_8U)
			for x in range(width) :
				for y in range(height) :
					history[x,y] = MAX
		else :
			width, height = self.get_wh(motionframe)

		for x in range(width) :
			for y in range(height) :
				if motionframe[x,y] > 0 :
					history[x,y] = 0
				else :
					if history[x,y] != MAX :
						history[x,y] += 1

		return history

	def ratio_lte_thr(self, img, thr) :
		width, height = self.get_wh(img)
		c = 0
		for x in range(width) :
			for y in range(height) :
				if img[x,y] <= thr :
					c += 1
		return c / float(width * height)

	def deactivate(self) :
		if self.zmq_url is not None :
			self.active = False
		else :
			self.stop()

	def stop(self) :
		self.ok = False
		if hasattr(self, 'streamer') :
			self.streamer.stop()

	def join(self) :
		if hasattr(self, 'streamer') and isinstance(self.streamer, threading.Thread):
			self.streamer.join()
		threading.Thread.join(self)

	def connect(self) :
		if hasattr(self, 'streamer') :
			self.streamer.stop()
			self.streamer.join()
		self.streamer = zmstream.ZMThrottle(1, self.url, auth=self.auth, zm_auth_hash_secret=self.zm_auth_hash_secret, mode=self.mode)
		self.streamer.start()

	@property
	def busy(self) :
		if self.ok :
			if self.ratio_busy is None or self.frame_time is None :
				# no history or no frame at all has been acquired
				return None

			if self.frame_time < time.time() - SEC_BEFORE_UNK :
				return None

			return self.ratio_busy

	def ratio_reaction(self) :
		for alert in self.alerts :
			alert.evaluate()

	# move to a base
	def checkedwait(self, secs) :
		for i in range(secs * 10) :
			if not self.ok :
				break
			time.sleep(0.1)

	def run_zmq(self) :
		import zmq
		c = zmq.Context(1)
		s = c.socket(zmq.SUB)
		s.connect(self.zmq_url)
		s.setsockopt (zmq.SUBSCRIBE, "")

		while self.ok :
			r, w, x = zmq.core.poll.select([s], [], [], 0.1)
			if r :
				msg = s.recv()

				msg = json.loads(msg)
				if msg['camname'] == self.camname :
					self.frame_time = msg['frame_time']
					self.ratio_busy = msg['ratio_busy']
					self.ratio_reaction()

	@property
	def live_ratio(self) :
		if self.zmq_url is not None :
			return True
		return self.ok

	def run(self) :
		zmq_socket = None
		if self.zmq_url is not None :
			if self.active :
				import zmq
				c = zmq.Context(1)
				zmq_socket = c.socket(zmq.PUB)
				zmq_socket.bind(self.zmq_url)
			else :
				self.run_zmq()
				return

		edge_bin = {}
		history = None

		while self.ok :
			try :
				self.connect()
				for ts, i in self.streamer.generate() :
					if not self.ok :
						return

					# TODO stop doing frame_time early when we may fail in this loop? grep all code
					self.frame_time = ts

					img = self.image_pil(i)

					filtered = self.filter_edges(img)
					#cv.SaveImage('edges.png', filtered)

					new_bin = self.bin_edgecount(filtered)

					diff = self.dict_diff(new_bin, edge_bin)
					edge_bin = new_bin

					motion_image = self.bins_to_img(diff)
					if motion_image :
						blob_motion = self.filter_for_blobs(motion_image)
						#cv.SaveImage('motion.png', blob_motion)

						history = self.frames_ago(blob_motion, history)

						self.ratio_busy = self.ratio_lte_thr(history, BUSY_THR)
						if zmq_socket is not None :
							msg = {
								'camname' : self.camname,
								'ratio_busy' : self.ratio_busy,
								'frame_time' : ts
							}
							zmq_socket.send(json.dumps(msg))
						print 'ratio busy %0.3f: %s' % (self.ratio_busy, self.camname)
						self.ratio_reaction()
						#cv.SaveImage('cumulative.png', history)

					# TODO fitful sleep that checks self.ok
					wait = max(0, 1.0/FPS + ts - time.time())
					time.sleep(wait)
			except zmstream.Timeout :
				print 'timed out on stream, re-acquiring'
			except zmstream.SocketError :
				print 'socket error, re-acquiring in %d.' % SOCKET_RETRY_SEC
				self.checkedwait(SOCKET_RETRY_SEC)

class Alert(object) :
	def __init__(self, p, mode, level, message, throttle, duration=None) :
		self.ok = True
		self.percept = p
		self.percept.alerts.append(self)
		self.mode = mode
		self.level = level
		self.message = message
		self.throttle = throttle
		self.duration = duration

		# outbound alerts state
		self.announce_time = 0.0
		self.q = Queue.Queue()

		# instant mode state
		self.active = False

		# sustained mode state
		self.sus_start = None

	def stop(self) :
		self.ok = False

	def evaluate(self) :
		if self.ok :		
			ratio = self.percept.busy

			new_active = ratio is not None and round(ratio * 100) > self.level

			if self.mode == 'instant' :
				old_active = self.active
				self.active = new_active
			elif self.mode == 'sustain' :
				self.active = new_active

				if self.active :
					if self.sus_start is None :
						self.sus_start = time.time()
				else :
					self.sus_start = None

			# no matter what you just decided to say, shut up if you're talking too much
			if time.time() < self.announce_time + self.throttle :
				return

			alerted = False
			if self.mode == 'instant' :
				alerted = self.active and not old_active
			elif self.mode == 'sustain' :
				alerted = self.sus_start is not None and self.sus_start < time.time() - self.duration

			if alerted :
				self.announce_time = time.time()
				self.q.put(self.message)
