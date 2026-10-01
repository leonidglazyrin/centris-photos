#!/usr/bin/env bash
# French version: re-render only the frames that show text or the map (lang=fr),
# drop them over the English master's frames, and encode with the French voices.
set -u
cd "$(dirname "$0")"
FFMPEG=${FFMPEG:-/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2}
mkdir -p out/fr_text out/fr_frames
seq 0 300 6900 | xargs -P 3 -I{} bash -c 'node render.mjs --lang fr --localized out/fr_text --from {} --to $(({}+300)) > out/fr_text/log_{}.txt 2>&1'
grep -L "localized done" out/fr_text/log_*.txt | grep . && { echo "FR render incomplete"; exit 1; }
[ -f out/fr_frames/07200.jpg ] || "$FFMPEG" -y -loglevel error -i out/master_video.mp4 -q:v 1 out/fr_frames/%05d.jpg
cp out/fr_text/*.jpg out/fr_frames/
"$FFMPEG" -y -loglevel error -framerate 24 -i out/fr_frames/%05d.jpg -c:v libx264 -preset slow -tune film -b:v 2350k -pass 1 -passlogfile out/x264fr -an -f mp4 /dev/null
"$FFMPEG" -y -loglevel error -framerate 24 -i out/fr_frames/%05d.jpg -i out/final_mix_fr.wav -c:v libx264 -preset slow -tune film -b:v 2350k -pass 2 -passlogfile out/x264fr \
  -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart -shortest ../LA_DERNIERE_LANTERNE_1080p.mp4
echo "FR ALL DONE"
