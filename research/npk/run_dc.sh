#!/bin/sh
# Chay decompile_all.py trong docker py27unc voi uid hien tai
cd /tmp/py27/work
exec docker run --rm -u "$(id -u):$(id -g)" --env-file /tmp/py27/work/dc.env -v /tmp/py27/work:/work py27unc python2 /work/decompile_all.py "${1:-/work/src}"
