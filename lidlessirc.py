import time
import threading
import irclib

class LidlessIRC(irclib.SimpleIRCClient) :
	def __init__(self, server, nick, chan, percepts) :
		self.percepts = percepts
		self.dead = False
		
		irclib.SimpleIRCClient.__init__(self)
		self._server = server
		self._nick = nick
		self._chan = chan

	def conn(self) :
		self.disconnecting = False
		self.connect(self._server, 6667, self._nick)
		self.connection.join(self._chan)
	
	def clean_shutdown(self) :
		if not self.disconnecting :
			self.disconnecting = True
			try :
				self.disconnect("lidless exiting")
			except :
				pass
		print 'shut down cleanly'
		self.dead = True
	
	def on_disconnect(self, c, e) :
		print 'got disconnect'
		self.dead = True

	def on_join(self, c, e) :
		pass

	def on_pubmsg(self, c, e) :
		chan = e.target()
		txt = e.arguments()[0]

		if txt == '!space' :
			if not self.percepts :
				msg = 'no cameras.'
			else :
				msgs = []
				for pname in self.percepts :
					bus = percepts[pname].busy

					if bus is None :
						state = "unknown"
					else :
						state = '%d%% busy' % round(bus * 100)

					msgs.append('%s: %s' % (pname, state))
				msg = ', '.join(msgs)
			
			self.connection.privmsg(chan, msg)

class IRCThread(threading.Thread) :
	def __init__(self, server, nick, chan, perc) :
		self.server = server
		self.nick = nick
		self.chan = chan
		self.perc = perc
		self.ok = True
		threading.Thread.__init__(self)

	def stop(self) :
		self.ok = False
		self.client.clean_shutdown()
		time.sleep(1)

	def run(self) :
		while self.ok :
			print 'creating new irc connection'
			self.client = LidlessIRC(self.server, self.nick, self.chan, self.perc)
			self.client.conn()

			while not self.client.dead :
				self.client.ircobj.process_once(0.2)
