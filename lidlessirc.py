import time
import mediorc
import Queue

class LidlessBot(mediorc.IRC) :
	def __init__(self, server, nick, chan, percepts, alerts) :
		self.percepts = percepts
		self.alerts = alerts
		mediorc.IRC.__init__(self, server, nick, chan)

	def on_pubmsg(self, c, e) :
		chan = e.target()
		txt = e.arguments()[0]

		if txt == '!space' :
			if not self.percepts :
				msg = 'no cameras.'
			else :
				msgs = []
				for pname in self.percepts :
					bus = self.percepts[pname].busy

					if bus is None :
						state = "unknown"
					else :
						state = '%d%% busy' % round(bus * 100)

					msgs.append('%s: %s' % (pname, state))
				msg = ', '.join(msgs)
			
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
