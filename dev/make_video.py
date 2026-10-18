"""Developer helper: frames from dev/record.ps1 -> mp4, with Blender's video sequencer (no ffmpeg needed).
    blender -b --factory-startup --python dev/make_video.py -- <frames dir> <out.mp4> <fps> [x0 y0 x1 y1]
The crop (default the game's client area, 8 31 1288 751) is in window pixels. The frames are written at <fps>."""
import glob
import os
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
frames_dir, out, fps = os.path.abspath(args[0]), os.path.abspath(args[1]), float(args[2])
box = [int(v) for v in args[3:7]] if len(args) >= 7 else [8, 31, 1288, 751]
files = sorted(glob.glob(os.path.join(frames_dir, "f*.jpg")))
assert files, "no frames"

scene = bpy.context.scene
w, h = box[2] - box[0], box[3] - box[1]
scene.render.resolution_x, scene.render.resolution_y = w - w % 2, h - h % 2
scene.render.resolution_percentage = 100
scene.render.fps = int(round(fps))
scene.render.fps_base = scene.render.fps / fps
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "HIGH"
scene.render.ffmpeg.ffmpeg_preset = "GOOD"
scene.render.ffmpeg.audio_codec = "NONE"
scene.render.filepath = out
seq = scene.sequence_editor_create()
first = bpy.data.images.load(files[0])
fw, fh = first.size
strip = seq.sequences.new_image("frames", files[0], channel=1, frame_start=1)
for f in files[1:]:
    strip.elements.append(os.path.basename(f))
strip.transform.offset_x = 0
strip.crop.min_x, strip.crop.max_x = box[0], fw - box[2]
strip.crop.max_y, strip.crop.min_y = box[1], fh - box[3]
strip.transform.offset_x = -(box[0] - (fw - box[2])) / 2
strip.transform.offset_y = (box[1] - (fh - box[3])) / 2
scene.frame_start, scene.frame_end = 1, len(files)
bpy.ops.render.render(animation=True)
print("VIDEO", out, len(files), "frames", w, h)
