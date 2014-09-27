import Queue
import time
import threading
from zmqfan import zmqsub

class LidlessAnnouncer(threading.Thread) :
	def __init__(self, alerts, zmq_url) :
		self.alerts = alerts
		self.zmqpub = zmqsub.ConnectPub(zmq_url)
		self.ok = True
		threading.Thread.__init__(self)
	
	def stop(self) :
		self.ok = False

	def run(self) :
		while self.ok :
			time.sleep(1)
			for alert in self.alerts :
				try :
					alert = alert.q.get(timeout=0)
					self.zmqpub.send({'text' : alert, 'pitch' : -180})
				except Queue.Empty :
					pass
