<A name="toc1-0" title="What's This?" />
# What's This?

lidless is a program for monitoring motion-jpeg camera feeds and interfacing them to IRC and the web, allowing users to request info on how busy the view captured by the cameras are and view historical information about busyness.

<A name="toc1-5" title="Dependencies" />
# Dependencies

* zmstream (https://github.com/eastein/zmstream)
* ramirez (https://github.com/eastein/ramirez)
* flot, as a git submodule.  To make this work, you must run 'git submodule init' / 'git submodule update'.
* OpenCV with python support, 2.1 or 2.2 work.  2.3 may work, but has not been tested successfully.
* CPython 2.6 or 2.7 (other pythons may work as well)
* python-irclib

You'll want a ZoneMinder server for this to be useful for a wide variety of camera streams, or if you have a motion jpeg http streaming camera, you will probably be able to use it directly.

<A name="toc1-17" title="Video Sources" />
# Video Sources

Please see the README for the version of `zmstream` you are using to determine what cameras and video sources will be supported by your install.

<A name="toc2-22" title="PTZ Cameras" />
## PTZ Cameras

Be aware that if you are using a pan/tilt/zoom camera, lidless's motion data will produce bad data around the periods when you move the camera.  The algorithms for motion detection depend on the camera's view being of the same field of view at all times.

<A name="toc1-27" title="HOWTO" />
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

The username and password options work with HTTP basic authentication or ZoneMinder's time based authentication session at this time.  They are optional.  HTTPS does not work for camera sources.  If you want to go through ZoneMinder, the URL must end with auth= (the GET parameter for auth must be at the end), the zm_auth_hash_secret parameter must be added into the camera JSON stanza, and the password is the password in the ZoneMinder database (already hashed).

<A name="toc1-54" title="API" />
# API

See API document for details of the API.

<A name="toc1-59" title="See Also" />
# See Also

See CREDITS for props to people who helped out.
