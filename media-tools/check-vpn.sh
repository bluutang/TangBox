#!/bin/bash
# Is the CURRENT vpn exit allowed to fetch the shows still to download?
# Probes one video per show - a few seconds, no downloading. Re-run after each
# server change until everything reads OK.
#
# Background: these are Spanish-language dubs whose rights cover ~212 countries.
# Poland, the USA, Germany and France are NOT among them; Mexico, Spain, Canada,
# the UK and most of Latin America are.
probe() {  # name id
  local t
  t=$(yt-dlp --no-download --print "%(title)s" "https://www.youtube.com/watch?v=$2" 2>/dev/null)
  if [ -n "$t" ]; then printf "  OK       %-10s %s\n" "$1" "${t:0:50}"
  else printf "  BLOCKED  %-10s (this server cannot fetch it)\n" "$1"; fi
}
echo "checking current vpn exit..."
probe "Jorge"    QV6WHK9i7BU
probe "Franklin" aHy5LuhBW5I
probe "Barney"   gyVhh7VWCtc
probe "Blue"     CUK7mLicQ80
