from huggingface_hub import snapshot_download
import os

download_path = snapshot_download(repo_id="SWHL/RapidOCR")
target_path = os.path.join("models", "rapidocr")
os.makedirs(target_path, exist_ok=True)

for file in os.listdir(download_path):
    src = os.path.join(download_path, file)
    dst = os.path.join(target_path, file)
    if not os.path.exists(dst):
        os.rename(src, dst)

print("RapidOCR models saved to:", target_path)
