import time
import threading
import irclib

class LidlessIRC(irclib.SimpleIRCClient) :
	JOIN_TIMEOUT = 120
	PING_TIMEOUT = 120
	PING_FREQUENCY = 60

	def __init__(self, server, nick, chan, percepts) :
		self.percepts = percepts
		self.dead = False
		self._ping_s = None
		self._ping_r = None
		self._create_t = time.time()

		irclib.SimpleIRCClient.__init__(self)
		self._server = server
		self._nick = nick
		self._chan = chan

	def conn(self) :
		self.disconnecting = False
		self.connect(self._server, 6667, self._nick)
		self.connection.join(self._chan)

	def maybe_send_ping(self) :
		if self._ping_s is None or self._ping_r is None :
			return

		if time.time() > self._ping_s + LidlessIRC.PING_FREQUENCY :
			self.connection.ping(self.connection.real_server_name)
			self._ping_s = time.time()

	@property
	def pinged_out(self) :
		if self._ping_s is None or self._ping_r is None :
			return time.time() - self._create_t > LidlessIRC.JOIN_TIMEOUT

		return time.time() - self._ping_r > LidlessIRC.PING_TIMEOUT

	def on_pong(self, c, e) :
		self._ping_r = time.time()

	def clean_shutdown(self) :
		if not self.disconnecting :
			self.disconnecting = True
			try :
				self.disconnect("lidless exiting")
			except :
				pass
		print 'irc shut down cleanly'
		self.dead = True
	
	def on_disconnect(self, c, e) :
		print 'got disconnect'
		self.dead = True

	def on_join(self, c, e) :
		if self._ping_s is None or self._ping_r is None :
			self._ping_s = time.time()
			self._ping_r = time.time()

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

class IRCThread(threading.Thread) :
	RETRY_SEC = 10

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

	# move to a base
	def checkedwait(self, secs) :
		for i in range(secs * 10) :
			if not self.ok :
				break
			time.sleep(0.1)

	def run(self) :
		while self.ok :
			print 'creating new irc connection'
			self.client = LidlessIRC(self.server, self.nick, self.chan, self.perc)
			try :
				self.client.conn()
			except irclib.ServerConnectionError :
				print 'could not connect to irc server for some reason, retrying in %d' % IRCThread.RETRY_SEC
				self.checkedwait(IRCThread.RETRY_SEC)

			while self.ok and not self.client.dead and not self.client.pinged_out :
				self.client.maybe_send_ping()
				self.client.ircobj.process_once(0.2)

			if self.ok :
				print 'shutting down irc connection before reconnect'
				self.client.clean_shutdown()
