#!/bin/bash

# Install FFmpeg
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz
tar -xf ffmpeg.tar.xz
mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg
mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe
chmod +x /usr/local/bin/ffmpeg
chmod +x /usr/local/bin/ffprobe

# Install dependencies with specific Pillow version
pip install --no-cache-dir -r requirements.txt
