import threading
import tornado.web
import tornado.ioloop

class JSONHandler(tornado.web.RequestHandler):
	@property
	def percs(self) :
		return self.application.__percepts__

	def wj(self, j) :
		self.write(j)

	def get(self, *a):
		error = None
		try :
			resp = {'status' : 'ok', 'data' : self.process_request(*a)}
		except KeyError :
			error = 'not found'
		except :
			error = 'exception'

		if error :
			resp = {'status' : 'failure', 'reason' : error}

		self.wj(resp)


class ListHandler(JSONHandler):
	def process_request(self):
		return self.percs.keys()

class CamHandler(JSONHandler):
	def process_request(self, camname):
		if camname not in self.percs :
			raise KeyError
		return ['ratio']

class RatioHandler(JSONHandler):
	def process_request(self, camname):
		return self.percs[camname].ratio_busy

class LidlessWeb(threading.Thread) :
	def __init__(self, percepts) :
		self.percepts = percepts
		threading.Thread.__init__(self)

	def run(self) :
		self.application = tornado.web.Application([
			(r"/$", ListHandler),
			(r"/([^/]+)/$", CamHandler),
			(r"/([^/]+)/ratio/$", RatioHandler),
		])
		self.application.__percepts__ = self.percepts
		self.application.listen(8000)


		self.io_instance = tornado.ioloop.IOLoop.instance()
		self.io_instance.start()

	def stop(self) :
		self.io_instance.stop()
