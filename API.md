<A name="toc1-0" title="lidless Web API" />
# lidless Web API

<A name="toc2-3" title="Basics" />
## Basics

* API shall be JSON over HTTP.

<A name="toc2-8" title="Terms" />
## Terms

* camera name: alphanumeric, underscores, hyphens. A unique identifier in the lidless install for a camera.
* busy ratio: a floating point number, between 0 and 1 (inclusive).
* capability: alphanumeric string that is a name for a function the camera supports.

<A name="toc2-15" title="Requests" />
## Requests

All requests shall be GET.  No authentication shall be required.

* /api: return list of camera names available
* /api/camname: return list of camera capabilities.  Capabilities can be accessed via /api/camname/capname.
* /api/camname/ratio: get current ratio.  Will be a floating point number if it's available.  Range between 0 and 100, inclusive.
* /api/camname/light: get current light level.  Will be a floating point number if it's available.  Range between 0 and 100, inclusive.
* /api/camname/ticks: get 1 hour of ratio history in raw form.  To be documented.
* /api/camname/history: get 1 hour of ratio history in binned average form.  To be documented.
* /api/camname/history/range_ms: get range_ms of ratio history in binned average form.  To be documented.

<A name="toc1-28" title="lidless ZeroMQ API" />
# lidless ZeroMQ API

Cameras that include a `zmq_url` parameter will engage their ZeroMQ API mode.  JSON objects will be sent over the socket after every frame that results in busyness measurements being recorded.

    {
      "camname" : "warehouse",
      "ratio_busy" : 0.0087316176470588237,
      "frame_time" : 1322038719.3862939,
      "luminance" : 187.842724,
      "busy_cells" : [[True, False, False, ...], [True, ...], ...]
    }

The above example is for a camera called warehouse that's 0.87% busy.  `frame_time` is a UTC unix timestamp with sub-second precision that indicates the time of retrieval of the most recent image frame that the data is based on.  The Indexing in the `busy_cells` is `object["busy_cells"][x][y]`.  If the value is True, it means that cell was busy at the time; do not expect `ratio_busy` to match up with the total ratio of True/False counts as the `ratio_busy` measure is based on some history as well.  `luminance` is on a scale of 0 to 255 and is the average luminance of the last frame received.
