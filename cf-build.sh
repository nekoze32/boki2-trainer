#!/bin/sh
# Cloudflare Pages のビルド。公開するファイルだけを site/ に集める（src/ の問題原本は配らない）
set -e
rm -rf site && mkdir site
cp index.html manifest.webmanifest *.png site/
