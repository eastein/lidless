# What's This?

lidless is a program for monitoring a ZoneMinder camera feed and interfacing it to IRC and the web, allowing users to request info on how busy the view captured by the camera is and view historical information about busyness.

# Dependencies

* zmstream (https://github.com/eastein/zmstream)
* ramirez (https://github.com/eastein/ramirez)
* flot, as a git submodule.  To make this work, you must run 'git submodule init' / 'git submodule update'.
* OpenCV with python support, 2.1 or greater
* CPython 2.6 or 2.7 (other pythons may work as well)
* python-irclib

You'll need a ZoneMinder server for this to be useful, although it may work with motion-jpeg http streams.

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

# API

See API document for details of the API.
