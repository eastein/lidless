# What's This?

lidless is a program for monitoring motion-jpeg camera feeds and interfacing them to IRC and the web, allowing users to request info on how busy the view captured by the cameras are and view historical information about busyness.

# Dependencies

* zmstream (https://github.com/eastein/zmstream)
* mediorc (https://github.com/eastein/mediorc)
* ramirez (https://github.com/eastein/ramirez)
* PIL
* flot, as a git submodule.  To make this work, you must run 'git submodule init' / 'git submodule update'.
* pyzmq (http://www.zeromq.org/bindings:python) if you use the `zmq_url` setting anywhere.
* pyffmpeg (http://code.google.com/p/pyffmpeg/) if you use the `use_ffmpeg` setting anywhere.
* OpenCV with python support, 2.1 or 2.2 work.  2.3 may work, but has not been tested successfully.
* CPython 2.6 or 2.7 (other pythons may work as well)
* python-irclib
* tornado (http://www.tornadoweb.org/)

Anything under https://github.com/eastein should be pulled/updated from github at the same time; from time to time, I change the way modules and their users work in fundamental ways.

You'll want a ZoneMinder server for this to be useful for a wide variety of camera streams, or if you have a motion jpeg http streaming camera, you will probably be able to use it directly.

# Video Sources

Please see the README for the version of `zmstream` you are using to determine what cameras and video sources will be supported by your install.

## PTZ Cameras

Be aware that if you are using a pan/tilt/zoom camera, lidless's motion data will produce bad data around the periods when you move the camera.  The algorithms for motion detection depend on the camera's view being of the same field of view at all times.

# HOWTO

You'll want to write a config file in JSON.

Here is an example:

    [{
      "type" : "camera",
      "name" : "warehouse",
      "url" : "http://1.2.3.4/mjpg/video.mjpg",
      "username" : "john",
      "password" : "doe"
    },
    {
      "type" : "irc",
      "server" : "irc.example.org",
      "nick" : "someguy",
      "channel" : "#irc"
    },
    {
      "type" : "web",
      "port" : 8000
    }]

The username and password options work with HTTP basic authentication or ZoneMinder's time based authentication session at this time.  They are optional.  HTTPS does not work for camera sources.  If you want to go through ZoneMinder, the URL must end with auth= (the GET parameter for auth must be at the end), the `zm_auth_hash_secret` parameter must be added into the camera JSON stanza, and the `username`/`password` should be a valid user in the ZoneMinder instance.

# Alerts

These only make sense if you have an `irc` or `announced` stanza.  See the *roles* section for more about making an alert go to more than one output.

    {
      "role" : ["announcer", "frontend"],
      "type" : "alert",
      "mode" : "sustain",
      "high_level" : 0,
      "duration" : 73200,
      "message" : "I've been sitting here in the woodshop for like a day and nobody came in. Will nobody touch my     wood?",
      "camera" : "woodshop",
      "throttle" : 86400
    }

How the `high_level`, `low_level` and `mode` settings here work will be documented later; for now, refer to the code in `percept.py` that concerns alerts.  The `throttle` parameter will prevent the alert from firing more often than every that-many seconds.

## announced

The program announced is a simple system for recieving textual commands that are spoken via text to speech.  If you have one running and would like to make alerts be sent over it, you can create an `announced` stanza, like so:

    {
      "role" : "announcer",
      "type" : "announced",
      "zmq_url" : "tcp://10.100.0.16:4503"
    }

See the *roles* section on alert routing considerations.

## FFMPEG

*WARNING: EXPERIMENTAL*

If you have access to a stream that ffmpeg can open and does not require authentication you can add the setting `mode = ffmpeg` to a `camera` stanza.  Doing so will use pyffmpeg to input the stream.  This is experimental and does not work very well yet, if at all.  Use at your own risk (even more so than the rest of this application, which is also at your own risk of course).

### Caveats

* pyffmpeg segfaults if you point it at a motion-jpeg stream that requires authentication, at the very least. I don't know what else it crashes on or the origin of this crash.
* if your CPU can't keep up, non-key frames may end up skipped and cause the video picture to get corrupted; you have probably seen this running HD video on an old computer.  This is easy to discount when watching video with your eyes, but less easy for *lidless* to discard and account for.  There may be a way to work around this.  I expect that these scenarios will result in falsely high busyness information or potentially falsely low busyness information.

## Roles

Different parts of the system can be run in separate processes to avoid contention and performance issues.  Roles are settings in a stanza that specify what role name a process must be running as in order to execute the work related to the stanza.

For a camera instance, this is reading the video stream, doing perceptual computations on it, and recording the data periodically.

For a web instance not using proxying (see below), the work is doing read operations on databases for historical data and shared memory access for the ratio data (there are issues currently with a web instance or irc instance accessing the current ratio of a camera not running in the same role, as it must use the database to access this information at this time).  A process can only have one role: the default role is called `default`.

An IRC instance will consume all alerts produced in its role, as will an announced instance.  You must run IRC and announced in separate processes (and hence, roles).  If you want alerts to go to more to than one, set the role on the alert stanza to a list of roles containing the consumers of alerts that you are targetting.  This has the added bonus feature (it's not a bug, really!) that you can send alerts to a specific subset of alert transmitting mediums.

## Proxying

If you are having web interface or API performance issues, it's suggested to add a second web stanza with the `proxy_endpoint` set to the base url of the other web stanza; in the above example such a `proxy_endpoint` setting would be `"http://localhost:8000"`.  A stanza that works for proxying is:

    {
      "role" : "webserver",
      "type" : "web",
      "proxy_mode" : "auto",
      "port" : 8000
    }

This proxying web instance has some special settings in play.  It is using the webserver role, which means it will not run in the `default` process: you must run another process with a role argument of `webserver` in order to execute it, using the same configuration file as the other processes.  It depends on every other process/role that services `camera` stanzas to also include a non-proxied `web` instance to do the actual data access.  The usage of the `proxy_mode = auto` setting will direct the proxy to load balance non-camera-specific requests and direct the camera-specific requests to the other `web` instance running on the local machine that is in the same `role` as the `camera` that the request is in reference to.  However, `proxy_mode = auto` does not currently work except over localhost.  If your worker processes are on a different machine than the proxy process, you will need to use `proxy_endpoint = http://ip:port` instead, and `proxy_mode = auto` isn't smart enough to automatically proxy between mid-layer proxies, so at this time proxying is not a solution for multi-machine scalability.

## Interchange in a Multi-role System

If not all of the stanzas have the same role, sometimes information is required in one stanza that is generated in a different stanza; for instance, current ratio information.  There are 3 ways that this information can be acquired: direct memory access (if the stanza needing the information is in the same python process), ZeroMQ PUB/SUB (this should work inter-machine), HTTP proxy.

### Direct Access

This one is the simplest; if the stanza (either `irc` or `web` that's doing serving and has no proxy settings configured) is in the same role, it will just access the data from the `camera` via the Python object that represents the camera processing work.

### ZeroMQ PUB/SUB

Setting the `zmq_url` parameter on a `camera` will set up a ZMQ PUB/SUB socket set internal to the camera that allows the inactive instances of the `camera` in the out-of-`role` processes to receive realtime updates on the current ratio.  This connects with the Direct Access system at that time such that other stanzas will just directly access the latest PUB/SUB interchanged ratio state.  For details of the messages sent over the `zmq_url`, see API.txt.

### HTTP Proxy

Using either `proxy_endpoint = ` or `proxy_mode = auto`, one `web` stanza can directly request the ratio data for API serving from a different `web` stanza that uses one of the other 2 methods of access.

# API

See API document for details of the API.

# See Also

See CREDITS for props to people who helped out.
