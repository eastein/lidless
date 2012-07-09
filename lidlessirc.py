import time
import mediorc
import Queue
import zmqsub

class LidlessBot(mediorc.IRC) :
	def __init__(self, server, nick, chan, percepts, alerts, endpoint) :
		self.percepts = percepts
		self.alerts = alerts
		self.endpoint = endpoint
		self.web_zmqs = {}
		mediorc.IRC.__init__(self, server, nick, chan)

	def route_web_zmq(self, camname) :
		if camname not in self.web_zmqs :
			zmqurl = self.endpoint.zmqendpoint(camname)
			self.web_zmqs[camname] = zmqsub.JSONZMQConnectPub(zmqurl)
		return self.web_zmqs[camname]
	
	def summarize_cameras(self, propname, noun) :
		if not self.percepts :
			msg = 'no cameras.'
		else :
			msgs = []
			for pname in self.percepts :
				bus = getattr(self.percepts[pname], propname)

				if bus is None :
					state = "unknown"
				else :
					state = '%d%% %s' % (round(bus * 100), noun)

				usename = getattr(self.percepts[pname], 'description', None)
				if usename is None :
					usename = pname
				msgs.append('%s: %s' % (usename, state))
			msg = ', '.join(msgs)
		return msg

	def on_pubmsg(self, c, e) :
		chan = e.target()
		words = e.arguments()[0].split(' ')

		msg = None
		if words[0] == '!space' :
			msg = self.summarize_cameras('busy', 'busy')
		elif words[0] == '!light' :
			msg = self.summarize_cameras('light', 'lit')
		elif words[0] in ['!snap', '!snapshot'] :
			# TODO work with the description of the camera
			try :
				pname = words[1]
				tsus = long(time.time() * 1000000)
				if pname not in self.percepts :
					msg = 'no such camera.'
				elif not self.percepts[pname].snapshot :
					msg = 'that camera does not allow snapshots'
				else :
					try :
						socket = self.route_web_zmq(pname)

						socket.send({
							"mtype"   : "snapshot_request",	
							"camname" : pname,
							"tsus"    : tsus
						})
						# TODO configurable base URL
						msg = 'sent request, should load at http://localhost:8000/api/%s/snapshot/%d.jpg' % (pname, tsus)
					except KeyError :
						msg = 'zmq_url is misconfigured for this camera, sorry.'
			except IndexError :
				camlist = [pn for pn in self.percepts.keys() if self.percepts[pn].snapshot]
				usage = 'usage: !snapshot <camname>'
				if camlist :
					usage += '. Cameras are: %s' % ', '.join(camlist)
				msg = usage
		if msg :
			self.connection.privmsg(chan, msg)

	def do_work(self) :
		for alert in self.alerts :
			try :
				alert = alert.q.get(timeout=0)
				self.connection.privmsg(self._chan, alert)
			except Queue.Empty :
				pass

class LidlessBotThread(mediorc.IRCThread) :
	def __init__(self, server, nick, chan, percepts, alerts, endpoint) :
		self.bot_create = lambda: LidlessBot(server, nick, chan, percepts, alerts, endpoint)
		mediorc.IRCThread.__init__(self)
