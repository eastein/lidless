import time
import mediorc

class LidlessBot(mediorc.IRC) :
	def __init__(self, server, nick, chan, percepts) :
		self.percepts = percepts
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

class LidlessBotThread(mediorc.IRCThread) :
	def __init__(self, server, nick, chan, percepts) :
		self.bot_create = lambda: LidlessBot(server, nick, chan, percepts)
		mediorc.IRCThread.__init__(self)
