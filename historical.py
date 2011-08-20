import threading
import Queue
import ramirez.mcore.events
import ramirez.mcore.trace

class History(threading.Thread) :
	def __init__(self, percept, ms=60000, err_ms=1000) :
		self.percept = percept
		self.ms = ms
		self.err_ms = err_ms
		self.ok = True
		self.q = Queue.Queue()
		threading.Thread.__init__(self)

	def stop(self) :
		self.ok = False
		self.q.put(None)

	def run(self) :
		self.history_trace = ramirez.mcore.trace.Trace(self.percept.camname , "%s.db" % self.percept.camname, self.ms, self.err_ms, 0)

		while self.ok :
			ratio = self.percept.busy
			if ratio is not None :
				self.history_trace.write(round(ratio * 100))

			try :
				self.q.get(timeout=(self.ms / 1000.0))
			except Queue.Empty :
				continue
