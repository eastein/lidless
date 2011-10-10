import sys
import threading
import traceback
import httplib
import tornado.web
import tornado.ioloop
import tornado.httpclient
import concurrent.futures as futures
import ramirez.mcore.events
import os.path

class RequestSharer() :
	def __init__(self, endpoint) :
		self.endpoint = endpoint
		self.rdict = dict()
		self.rlock = threading.Lock()

	"""
	Returns whether a request is already underway or whether one must be started
	"""
	def register(self, url, inbound) :
		with self.rlock :
			if url in self.rdict :
				self.rdict[url].append(inbound)
				return True
			else :
				self.rdict[url] = [inbound]
				return False

	def respond(self, url, response) :
		with self.rlock :
			err = False
			if response.error :
				print 'error retrieving %s' % url
				code = response.code
				body = response.body
				headers = response.headers
				err = True
			else :
				code = response.code
				body = response.body
				headers = response.headers
			
			for inb in self.rdict[url] :
				try :
					if response.code in httplib.responses :
						inb.set_status(response.code)
					else :
						print 'WARNING response.code = %s, sending 500' % str(response.code)
						# capacity issue?
						inb.set_status(500)

					for header in headers :
						inb.set_header(header, headers[header])
					if body :
						inb.write(body)
					elif err :
						# TODO handle this better, there are many errcodes
						inb.write("Error proxying")
					
					inb.finish()
				except :
					print 'exception while trying to send proxy response for %s' % url
					traceback.print_exc()

			del self.rdict[url]

class ProxyingHandler(tornado.web.RequestHandler):
	@tornado.web.asynchronous
	def get(self, url) :
		print '[proxyinghandler] GET %s' % url
		if not self.application.__requestsharer__.register(url, self) :
			http_client = tornado.httpclient.AsyncHTTPClient()
			h = lambda resp: self.application.__requestsharer__.respond(url, resp)
			http_client.fetch(self.application.__requestsharer__.endpoint + url, h, request_timeout=120.0)

class ProtoFuture(object) :
	def __init__(self, fut, continuation) :
		#print 'ProtoFuture.__init__'
		self.fut = fut
		self.continuation = continuation
		self.cbs = []
		self.fut.add_done_callback(self.completed)

	def add_done_callback(self, cb) :
		#print 'ProtoFuture.add_done_callback'
		self.cbs.append(cb)

	def completed(self, fut) :
		#print 'ProtoFuture.completed'
		for cb in self.cbs :
			cb(self)

	def result(self) :
		#print 'ProtoFuture.result'
		return self.continuation(self.fut.result())

class JSONHandler(tornado.web.RequestHandler):
	@property
	def percs(self) :
		return self.application.__percepts__

	def wj(self, j) :
		self.application.__io_instance__.add_callback(lambda: self._wj(j))

	def _wj(self, j) :
		self.write(j)
		self.finish()

	@tornado.web.asynchronous
	def get(self, *a):
		result = self.process_request(*a)
		if isinstance(result, (futures.Future, ProtoFuture)) :
			result.add_done_callback(self.handle_response)
		else :
			self.handle_response(result)

	def handle_response(self, result) :
		error = None
		try :
			if isinstance(result, (futures.Future, ProtoFuture)) :
				result = result.result()
			
			resp = {'status' : 'ok', 'data' : result}
		except ValueError :
			error = 'bad input'
		except KeyError :
			error = 'not found'
		except :
			print 'exception while fetching deferred result'
			traceback.print_exc()
			error = 'exception'

		if error :
			resp = {'status' : 'failure', 'reason' : error}

		self.wj(resp)

class JSHandler(tornado.web.RequestHandler):
	def get(self, fn):
		if not hasattr(self.__class__, 'fcache') :
			self.__class__.fcache = {}

		if fn in self.__class__.fcache :
			self.write(self.__class__.fcache[fn])
		else :
			ffn = os.path.join('flot', fn)
			if not os.path.exists(ffn) :
				raise tornado.web.HTTPError(404)
			d = open(ffn).read()
			self.__class__.fcache[fn] = d
			self.write(d)

class ListHandler(JSONHandler):
	def process_request(self):
		return self.percs.keys()

class CamHandler(JSONHandler):
	def process_request(self, camname):
		if camname not in self.percs :
			raise KeyError
		cap = ['ratio']
		if hasattr(self.percs[camname], 'history') :
			cap.append('history')
			cap.append('ticks')
		return cap

class RatioHandler(JSONHandler):
	def process_request(self, camname):
		return self.percs[camname].busy

class TicksHandler(JSONHandler):
	def process_request(self, camname):
		s, e, ticks = self.percs[camname].history.history(3600 * 1000)
		cont = lambda hist: [t.asdict for t in hist]
		return ProtoFuture(ticks, cont)

class HistoryHandler(JSONHandler):
	def process_request(self, camname, ms_range=3600*1000):
		# ms must evenly divide into bins for this logic to be valid!
		# FIXME constrain that
		# ms must be even, probably
		self._ms_range = long(ms_range)
		self._nbins = 120

		self._bin_ms = self._ms_range / self._nbins
		self._bins = [list() for i in range(self._nbins)]

		hist = self.percs[camname].history.history(self._ms_range)

		if hist is None :
			# this means that the historical trace is not started. give up.
			raise tornado.web.HTTPError(501)
		
		# get start time end time and tick data
		self._s, self._e, ticks = hist
		return ProtoFuture(ticks, self.bin_ticks)

	def bin_ticks(self, ticks) :
		ms_range = self._ms_range
		nbins = self._nbins
		bin_ms = self._bin_ms
		ms_range = self._ms_range
		bins = self._bins

		s = self._s
		e = self._e

		bin_bounds = [(s + bin_ms * i, s + bin_ms * (i + 1)) for i in range(nbins)]
		bin_mids = [s + bin_ms * i + bin_ms / 2 for i in range(nbins)]

		for tick in ticks :
			# when the tick starts
			ts = tick.start_ms
			# when the tick's influence ends (tick period past the last sample)
			te = tick.end_ms + tick.tick_ms

			# compute the total number of ms in the tick
			ms = te - ts
			# compute total number of samples in the tick (votes)
			samples = (tick.end_ms - tick.start_ms) / tick.tick_ms + 1

			# compute the range of bin indexes that this tick has influence in
			bin_begin = max(0, long(ts - s) / bin_ms)
			bin_end = min(nbins - 1, long(te - s) / bin_ms)

			for bin in range(bin_begin, bin_end + 1) :
				# now we know this tick has influence that falls within this bin. compute how much.
				overlap_s = max(ts, bin_bounds[bin][0])
				overlap_e = min(te, bin_bounds[bin][1])

				overlap_ms = overlap_e - overlap_s
				
				# ratio portion of the tick that falls within this bin
				tickpart = float(overlap_ms) / float(ms)
				# determine how many sample-votes the value can be cast with in the bin
				votes = samples * tickpart
				# cast vote in bin
				bins[bin].append((votes, tick.value))

		values = [0] * nbins

		# tally votes
		for bin in range(nbins) :
			votes = 0.0
			tvalue = 0.0
			
			for vote, value in bins[bin] :
				votes += vote
				tvalue += vote * value

			if votes <= 0.0 :
				continue
			
			values[bin] = tvalue / votes

		return zip(bin_mids, values)

class InterfaceHandler(tornado.web.RequestHandler) :
	def get(self) :
		self.write(self.application.__interface__)

class LidlessWeb(threading.Thread) :
	def __init__(self, percepts, port=8000, endpoint=None) :
		self.percepts = percepts
		self.port = port
		self.ok = True
		self.endpoint = endpoint
		threading.Thread.__init__(self)

	def run(self) :
		if not self.ok :
			return
		
		if not self.endpoint :
			self.application = tornado.web.Application([
				(r"/$", InterfaceHandler),
				(r"/flot/([a-z0-9\.\-]+\.js)$", JSHandler), # pattern is a security issue, be careful!
				(r"/api$", ListHandler),
				(r"/api/([^/]+)$", CamHandler),
				(r"/api/([^/]+)/ratio$", RatioHandler),
				(r"/api/([^/]+)/ticks$", TicksHandler),
				(r"/api/([^/]+)/history$", HistoryHandler),
				(r"/api/([^/]+)/history/([0-9]+)$", HistoryHandler),

			])
			self.application.__percepts__ = self.percepts
			self.application.__interface__ = open('interface.html').read()
		else :
			self.application = tornado.web.Application([
				(r"(/.*)$", ProxyingHandler),
			])

			self.application.__requestsharer__ = RequestSharer(self.endpoint)

		# TODO catch bind error here!
		self.application.listen(self.port)

		self.application.__io_instance__ = tornado.ioloop.IOLoop.instance()
		self.application.__io_instance__.start()

	def stop(self) :
		self.ok = False
		if hasattr(self, 'application') :
			if hasattr(self.application, '__io_instance__') :
				self.application.__io_instance__.stop()
