#!/usr/bin/env bash
# Renders the full film in 12 chunks with 3 parallel workers (resumable),
# then concatenates, muxes the score and encodes the deliverables.
set -u
cd "$(dirname "$0")"
FFMPEG=${FFMPEG:-/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2}
mkdir -p out/chunks
# Frame ranges: first half in 600-frame chunks, the rest in 120-frame chunks so
# a container restart loses at most a few minutes of work.
RANGES=$( (for s in $(seq 0 600 3000); do echo "$s $((s+600))"; done; for s in $(seq 3600 120 7080); do echo "$s $((s+120))"; done) )
render_chunk() {
  local f0=$1 f1=$2; local o=out/chunks/f$(printf %05d $f0).mp4
  [ -s "$o.done" ] && return 0
  node render.mjs --from $f0 --to $f1 --out "$o" > "${o%.mp4}.log" 2>&1 && echo ok > "$o.done"
}
export -f render_chunk
echo "$RANGES" | xargs -P 3 -L 1 bash -c 'render_chunk "$0" "$1"'
[ "$(ls out/chunks/*.done | wc -l)" -eq 36 ] || { echo "chunks missing"; exit 1; }
ls out/chunks/*.mp4 | sort | sed "s/^out\/chunks\//file '/; s/$/'/" > out/chunks/list.txt
"$FFMPEG" -y -loglevel error -f concat -safe 0 -i out/chunks/list.txt -c copy out/master_video.mp4
python3 music.py
# deliverable: 1080p, 2-pass to stay under GitHub's 100 MB file limit
"$FFMPEG" -y -loglevel error -i out/master_video.mp4 -c:v libx264 -preset slow -tune film -b:v 2350k -pass 1 -passlogfile out/x264 -an -f mp4 /dev/null
"$FFMPEG" -y -loglevel error -i out/master_video.mp4 -i out/score.wav -c:v libx264 -preset slow -tune film -b:v 2350k -pass 2 -passlogfile out/x264 \
  -c:a aac -b:a 160k -movflags +faststart -shortest ../THE_LAST_LANTERN_1080p.mp4
echo "ALL DONE"
