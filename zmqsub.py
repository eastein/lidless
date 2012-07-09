import zmq
import json

class NoMessagesException(Exception) :
	pass

class JSONZMQSub(object) :
	def __init__(self, url) :
		self.c = zmq.Context(1)
		self.s = self.c.socket(zmq.SUB)
		self.s.connect(url)
		self.s.setsockopt (zmq.SUBSCRIBE, "")
		self._last = None

	def last_msg(self) :
		r = [self.s]
		msg = None
		while r :
			r, w, x = zmq.core.poll.select([self.s], [], [], 0.0)
			if r :
				msg = self.s.recv()

		r, w, x = zmq.core.poll.select([self.s], [], [], 0.05)
		if r :
			msg = self.s.recv()

		if msg is not None :
			self._last = json.loads(msg)

		return self._last

	def recv(self) :
		msg = None
		r, w, x = zmq.core.poll.select([self.s], [], [], 0.0)
		if r :
			msg = self.s.recv()
			self._last = json.loads(msg)
			return self._last
		else :
			raise NoMessagesException
		
class JSONZMQBindSub(object) :
	def __init__(self, url) :
		self.c = zmq.Context(1)
		self.s = self.c.socket(zmq.SUB)
		self.s.bind(url)
		self.s.setsockopt (zmq.SUBSCRIBE, "")

	def recv(self) :
		msg = None
		r, w, x = zmq.core.poll.select([self.s], [], [], 0.0)
		if r :
			msg = self.s.recv()
			self._last = json.loads(msg)
			return self._last
		else :
			raise NoMessagesException

class JSONZMQBindPub(object) :
	def __init__(self, url) :
		self.c = zmq.Context(1)
		self.s = self.c.socket(zmq.PUB)
		self.s.bind(url)

	def send(self, msg) :
		self.s.send(json.dumps(msg))

class JSONZMQConnectPub(object) :
	def __init__(self, url) :
		self.c = zmq.Context(1)
		self.s = self.c.socket(zmq.PUB)
		self.s.connect(url)

	# unreliable send, but won't block forever.
	def send(self, msg) :
		r, w, x = zmq.core.poll.select([], [self.s], [], 10.0)
		if w :
			self.s.send(json.dumps(msg))
