#!/usr/bin/awk -f

BEGIN {
  n=0
}

n == 0 && $0 ~ /[A-Z0-9]{24} .* Release.xcconfig .* / {
  n=1
}

n == 1 && $0 ~ /PRODUCT_BUNDLE_IDENTIFIER = / {
  gsub(/;/, "", $NF)
  print $NF
  exit
}
