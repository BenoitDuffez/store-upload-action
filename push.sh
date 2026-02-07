#!/bin/bash

git push
git push github
for d in ls ~/.cache/act/*
do
  ls -l "$d/reframed.png" >/dev/null 2>&1 \
    && rm -vrf "$d"
done
