#!/usr/bin/env bash
# runs curl /leak to start leak (or run internal leak script)
curl -s http://127.0.0.1:8080/leak >/dev/null
