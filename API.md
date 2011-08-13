<A name="toc1-0" title="lidless API" />
# lidless API

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

* /: return list of camera names available
* /camname: return list of camera capabilities.  Capabilities can be accessed via /camname/capname/args.
* /camname/ratio: get current ratio.  Will be a floating point number if it's available, string error otherwise.
