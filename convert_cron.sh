#!/bin/bash

LOCK=/var/lock/docconvert
LOG=/usr/local/word2mediawiki/log/word2mediawiki.log

# Set the internal field separator (IFS) to not include spaces, enabling
# use of paths with spaces
ORIGINAL_IFS=$IFS
IFS=$'\n'

if [ "$(id -nu)" != "docconvert" ]; then
   echo This script must be run as user docconvert
   exit 1
fi

lockfile-create $LOCK
if [ $? -ne 0 ]; then
   echo Converter script already running, aborting
   exit 1
fi
lockfile-touch $LOCK &
LOCKTOUCHPID="$!"

date +"%Y-%m-%d %H:%M:%S Scanning directory..." >> $LOG
# If there are any files to convert, send them through the converter
cd /usr/local/word2mediawiki
FIRST=1
for OLDF in $(find share -type f) ; do
   date +"%Y-%m-%d %H:%M:%S Converting $OLDF..." >> $LOG
   if [ "$FIRST" == "1" ]; then
      # If there is an instance of openoffice running, get rid of it
      # (there should never be one)
      pkill -9 soffice.bin

      # Start open office in listening mode
      soffice --accept="socket,port=8100;urp;" --norestore --headless --nologo >>$LOG

      # For each run, sleep a while to make sure samba has finished
      # writing the file, and that openoffice has actually started.
      sleep 5
      FIRST=0
   fi

   # Get rid of strange characters
   F=$(echo "$OLDF" | iconv -f utf8 -t ascii//ignore)
   mv -v -f "$OLDF" "$F" >> $LOG

   python word2mediawiki.py "$F" >> $LOG 2>&1

   rm -f "$F"

   date +"%Y-%m-%d %H:%M:%S Done with $F, removing." >> $LOG
done

# Restore internal field separator original value
IFS=$ORIGINAL_IFS

# Get rid of our instance of openoffice
pkill soffice.bin

kill $LOCKTOUCHPID
lockfile-remove $LOCK
