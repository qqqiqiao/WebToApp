#!/bin/sh
# Prepare writable data dirs, then drop root. Volumes are often root-owned
# when they are first mounted, and the app must create apps and keystores.
set -eu
mkdir -p /app/generated /app/certs/app-keys /app/server/engine/_android_template
chown -R webtoapp:webtoapp \
  /app/generated \
  /app/certs/app-keys \
  /app/server/engine/_android_template
# PEM files are often created on the host as mode 600. The app user still
# needs to read them; only this container's users can.
if [ -d /app/certs ]; then
  find /app/certs -maxdepth 1 -type f -exec chmod a+r {} \;
fi
if [ -d /app/server/engine/_android_tools ]; then
  chown -R webtoapp:webtoapp /app/server/engine/_android_tools
fi
exec runuser -u webtoapp -- "$@"
