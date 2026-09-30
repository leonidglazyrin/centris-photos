#!/usr/bin/env bash
# Renders the full film in 12 chunks with 3 parallel workers (resumable),
# then concatenates, muxes the score and encodes the deliverables.
set -u
cd "$(dirname "$0")"
FFMPEG=${FFMPEG:-/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2}
mkdir -p out/chunks
CHUNK=600; TOTAL=7200; WORKERS=3
render_chunk() {
  local i=$1; local f0=$((i*CHUNK)); local f1=$(((i+1)*CHUNK))
  local o=out/chunks/c$(printf %02d $i).mp4
  [ -s "$o.done" ] && return 0
  node render.mjs --from $f0 --to $f1 --out "$o" > out/chunks/c$(printf %02d $i).log 2>&1 && echo ok > "$o.done"
}
export -f render_chunk; export CHUNK
seq 0 $((TOTAL/CHUNK-1)) | xargs -P $WORKERS -I{} bash -c 'render_chunk {}'
ls out/chunks/*.mp4 | sort | sed "s/^/file '/; s/$/'/; s/out\/chunks\///" > out/chunks/list.txt
"$FFMPEG" -y -loglevel error -f concat -safe 0 -i out/chunks/list.txt -c copy out/master_video.mp4
python3 music.py
# deliverable: 1080p, 2-pass to stay under GitHub's 100 MB file limit
"$FFMPEG" -y -loglevel error -i out/master_video.mp4 -c:v libx264 -preset slow -tune film -b:v 2350k -pass 1 -passlogfile out/x264 -an -f mp4 /dev/null
"$FFMPEG" -y -loglevel error -i out/master_video.mp4 -i out/score.wav -c:v libx264 -preset slow -tune film -b:v 2350k -pass 2 -passlogfile out/x264 \
  -c:a aac -b:a 160k -movflags +faststart -shortest ../THE_LAST_LANTERN_1080p.mp4
echo "ALL DONE"
