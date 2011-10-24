# What's This?

lidless is a program for monitoring motion-jpeg camera feeds and interfacing them to IRC and the web, allowing users to request info on how busy the view captured by the cameras are and view historical information about busyness.

# Dependencies

* zmstream (https://github.com/eastein/zmstream)
* mediorc (https://github.com/eastein/mediorc)
* ramirez (https://github.com/eastein/ramirez)
* flot, as a git submodule.  To make this work, you must run 'git submodule init' / 'git submodule update'.
* pyzmq (http://www.zeromq.org/bindings:python) if you use the `zmq_url` setting anywhere
* OpenCV with python support, 2.1 or 2.2 work.  2.3 may work, but has not been tested successfully.
* CPython 2.6 or 2.7 (other pythons may work as well)
* python-irclib
* tornado (http://www.tornadoweb.org/)

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

## Roles

Different parts of the system can be run in separate processes to avoid contention and performance issues.  Roles are settings in a stanza that specify what role name a process must be running as in order to execute the work related to the stanza.  For a camera instance, this is reading the video stream, doing perceptual computations on it, and recording the data periodically.  For a web instance not using proxying (see below), the work is doing read operations on databases for historical data and shared memory access for the ratio data (there are issues currently with a web instance or irc instance accessing the current ratio of a camera not running in the same role, as it must use the database to access this information at this time).  A process can only have one role: the default role is called `default`.

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

Setting the `zmq_url` parameter on a `camera` will set up a ZMQ PUB/SUB socket set internal to the camera that allows the inactive instances of the `camera` in the out-of-`role` processes to receive realtime updates on the current ratio.  This connects with the Direct Access system at that time such that other stanzas will just directly access the latest PUB/SUB interchanged ratio state.

### HTTP Proxy

Using either `proxy_endpoint = ` or `proxy_mode = auto`, one `web` stanza can directly request the ratio data for API serving from a different `web` stanza that uses one of the other 2 methods of access.

# API

See API document for details of the API.

# See Also

See CREDITS for props to people who helped out.
