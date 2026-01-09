#!/usr/bin/awk -f

BEGIN {
  FS="\""
}

/applicationId/ {
  print $(NF-1)
  exit
}
