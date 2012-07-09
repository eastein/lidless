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
import StringIO
import base64

SOCKET_RETRY_SEC = 10
NO_FRAME_THR = 10
BUSY_SEC = 120
SEC_BEFORE_UNK = 20
FPS = 1
#FIXME if BUSY_THR goes over the max number for the last-motion buffer, ratio will be 1.0 all the time
BUSY_THR = FPS * BUSY_SEC

class Percept(threading.Thread) :
	def __init__(self, camname, description, url, auth=None, zm_auth_hash_secret=None, zmq_url=None, mode=zmstream.Mode.MJPEG, snapshot=False, role=None) :
		self.camname = camname
		self.description = description
		self.url = url
		self.auth = auth
		self.zm_auth_hash_secret = zm_auth_hash_secret
		self.zmq_url = zmq_url
		self.mode = mode
		self.ok = True
		self.active = True
		self.frame_time = None
		self.ratio_busy = None
		self.luminance = None
		self.alerts = []
		self.snapshot = snapshot
		self.role = role
		threading.Thread.__init__(self)

	def image_frompil(self, pil_image) :
		cv_im = cv.CreateImageHeader(pil_image.size, cv.IPL_DEPTH_8U, 3)
		cv.SetData(cv_im, pil_image.tostring())
		return cv_im

	def filter_edges_luminance(self, img) :
		sz = cv.GetSize(img)
		bw = cv.CreateMat(sz[1], sz[0], cv.CV_8U)
		med = cv.CreateMat(sz[1], sz[0], cv.CV_8U)
		canny = cv.CreateMat(sz[1], sz[0], cv.CV_8U)
		cv.CvtColor(img, bw, cv.CV_RGB2GRAY)
		cv.Smooth(bw, med, cv.CV_MEDIAN, 5)
		cv.Canny(med, canny, 75, 112, 3)
		luminance = self.average_luminance(bw)
		return canny, luminance

	def dict_diff(self, d1, d2) :
		key_merge = set(d1.keys()).intersection(d2.keys())
		result = {}
		for k in key_merge :
			result[k] = abs(d1[k] - d2[k])
		return result
	
	def average_luminance(self, img) :
		sz = cv.GetSize(img)
		w, h = sz[1], sz[0]
		total = 0
		for x in range(w) :
			for y in range(h) :
				total += img[x, y]

		return total / float(w * h)

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

	def determine_busyness(self, img) :
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

	def record_frame(self, motionframe, history) :
		# TODO convert to milliseconds, use more bit depth to achieve it

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
						history[x,y] += 1 # TODO #7 do not assume 1 second here... quite wrong

		return history

	def time_decay(self, history, by_seconds) :
		# TODO convert to milliseconds, use more bit depth to achieve it
		
		MAX = 256 - 1

		sz = cv.GetSize(history)
		w, h = sz[1], sz[0]

		for x in range(w) :
			for y in range(h) :
				if history[x,y] != MAX :
					history[x,y] += by_seconds

	def busyness_array(self, motionframe) :
		width, height = self.get_wh(motionframe)

		r = list()

		for x in range(width) :
			col = list()
			r.append(col)
			for y in range(height) :
				if motionframe[x,y] > 0 :
					col.append(True)
				else :
					col.append(False)

		return r

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
	def light(self) :
		if self.ok :
			if self.luminance is None or self.luminance is None :
				# no history or no frame at all has been acquired
				return None

			if self.frame_time < time.time() - SEC_BEFORE_UNK :
				return None

			return self.luminance / 255.0

	@property
	def busy(self) :
		if self.ok :
			if self.ratio_busy is None or self.frame_time is None :
				# no history or no frame at all has been acquired
				return None

			if self.frame_time < time.time() - SEC_BEFORE_UNK :
				return None

			return self.ratio_busy

	@property
	def jpeg(self) :
		if self.ok :
			if self.frame_time < time.time() - SEC_BEFORE_UNK :
				return None
			
			if not self.snapshot :
				return None
			
			try :
				return self.jpeg_str
			except AttributeError :
				return None

	@property
	def busy_percentage(self) :
		ratio = self.busy
		if ratio is not None :
			return round(ratio * 100)

	def ratio_reaction(self) :
		for alert in self.alerts :
			alert.evaluate()

	# move to a base
	def checkedwait(self, secs) :
		for i in range(int(secs * 100)):
			if not self.ok :
				break
			time.sleep(0.01)

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

				if msg['mtype'] != "percept_update" :
					continue

				if msg['camname'] == self.camname :
					self.frame_time = msg['frame_time']
					self.ratio_busy = msg['ratio_busy']
					self.luminance = msg['luminance']
					if 'base64_jpeg' in msg :
						self.jpeg_str = base64.decodestring(msg['base64_jpeg'])
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
		luminance_change = 0.0

		while self.ok :
			try :
				self.connect()
				for ts, i in self.streamer.generate() :
					if not self.ok :
						return

					# TODO stop doing frame_time early when we may fail in this loop? grep all code
					self.frame_time = ts

					img = self.image_frompil(i)

					filtered, luminance = self.filter_edges_luminance(img)
					#cv.SaveImage('edges.png', filtered)

					if self.luminance is not None :
						# percent difference from the more luminant luminance
						luminance_change_abs = abs(self.luminance - luminance)
						larger_luminance = max(self.luminance, luminance)
						if larger_luminance < 1.0 :
							luminance_change = 0.0
						else :
							luminance_change = luminance_change_abs / larger_luminance

					new_bin = self.bin_edgecount(filtered)

					diff = self.dict_diff(new_bin, edge_bin)
					edge_bin = new_bin

					motion_image = self.bins_to_img(diff)
					if motion_image :
						if luminance_change < 0.7 : # TODO use a constant
							motion_buffer = self.determine_busyness(motion_image)
							#cv.SaveImage('motion.png', motion_buffer)

							# TODO #7; this function assumes a 1 second time interval which is not valid
							history = self.record_frame(motion_buffer, history)
						else :
							#print 'skipping recording to history for %s, luminance_change = %0.3f' % (self.camname, luminance_change)
							self.time_decay(history, 1) # TODO #7 use actual timing data here, not assume 1 second

						self.ratio_busy = self.ratio_lte_thr(history, BUSY_THR)
						if self.snapshot :
							img_sio = StringIO.StringIO()
							i.save(img_sio, format='jpeg')
							img_sio.seek(0)
							self.jpeg_str = img_sio.read()
						
						if zmq_socket is not None :
							msg = {
								'mtype' : "percept_update",
								'camname' : self.camname,
								'ratio_busy' : self.ratio_busy,
								'luminance' : luminance,
								'frame_time' : ts,
								'busy_cells' : self.busyness_array(motion_buffer)
							}
							if self.snapshot :
								msg['base64_jpeg'] = base64.encodestring(self.jpeg_str)
							
							zmq_socket.send(json.dumps(msg))

						print '%s frame processed, ratio busy %0.3f, lumr %1.3f lum %3.1f' % (self.camname.ljust(20), self.ratio_busy, luminance_change, luminance)
						self.ratio_reaction()
						#cv.SaveImage('cumulative.png', history)

					# record luminance for later comparison
					self.luminance = luminance
					spent = time.time() - ts
					wait = 1.0/FPS - spent
					if wait > 0.0 :
						self.checkedwait(wait)
			except zmstream.Timeout :
				print 'timed out on stream, re-acquiring'
			except zmstream.SocketError :
				print 'socket error, re-acquiring in %d.' % SOCKET_RETRY_SEC
				self.checkedwait(SOCKET_RETRY_SEC)

class Alert(object) :
	def __init__(self, p, mode, low_level, high_level, message, throttle, duration=None) :
		self.ok = True
		self.percept = p
		self.percept.alerts.append(self)
		self.mode = mode
		self.low_level = low_level
		self.high_level = high_level
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
			percentage = self.percept.busy_percentage

			new_active = False
			if percentage is not None :
				new_active = True
				if self.low_level is not None :
					new_active &= (percentage >= self.low_level)
				if self.high_level is not None :
					new_active &= (percentage <= self.high_level)

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
