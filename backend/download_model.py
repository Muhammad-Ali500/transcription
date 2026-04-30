#!/usr/bin/env python3
import os
import shutil
from huggingface_hub import snapshot_download

MODEL_NAME = "Systran/faster-whisper-large-v3"
OUTPUT_DIR = "/app/models/large-v3"

print(f"Downloading {MODEL_NAME}...")
cache_dir = "/tmp/hf_cache"
snapshot_download(MODEL_NAME, cache_dir=cache_dir)

# Find the snapshot directory
for d in os.listdir(cache_dir):
    if d.startswith("models--"):
        snapshot_path = os.path.join(cache_dir, d, "snapshots")
        if os.path.exists(snapshot_path):
            for snap in os.listdir(snapshot_path):
                src = os.path.join(snapshot_path, snap)
                if os.path.isdir(src):
                    shutil.copytree(src, OUTPUT_DIR)
                    print(f"Model saved to {OUTPUT_DIR}")
                    print(f"Files: {os.listdir(OUTPUT_DIR)}")
                    exit(0)

print("ERROR: Model not found in cache")
exit(1)
