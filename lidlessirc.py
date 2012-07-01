import time
import mediorc
import Queue

class LidlessBot(mediorc.IRC) :
	def __init__(self, server, nick, chan, percepts, alerts) :
		self.percepts = percepts
		self.alerts = alerts
		mediorc.IRC.__init__(self, server, nick, chan)

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
		txt = e.arguments()[0]

		msg = None
		if txt == '!space' :
			msg = self.summarize_cameras('busy', 'busy')
		elif txt == '!light' :
			msg = self.summarize_cameras('light', 'lit')

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
	def __init__(self, server, nick, chan, percepts, alerts) :
		self.bot_create = lambda: LidlessBot(server, nick, chan, percepts, alerts)
		mediorc.IRCThread.__init__(self)
