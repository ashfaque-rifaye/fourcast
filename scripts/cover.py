"""Generate the lablab cover image with FLUX.1 schnell on Fireworks.

    uv run python scripts/cover.py   ->  assets/cover.png (1024x576-ish, 16:9)
"""
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

PROMPT = (
    "Bold flat vector poster for an AI product called FOURCAST. A single glowing "
    "video play button at the center bottom, four stylized speech bubbles rising "
    "from it in four distinct moods: one clean and corporate, one with a wry "
    "smirk, one filled with circuit patterns, one with a coffee cup and sun. "
    "Deep navy background, vivid orange and warm gradient accents, subtle grid, "
    "modern tech-poster composition, crisp shapes, no photograph, minimal text."
)

ENDPOINTS = [
    "/workflows/accounts/fireworks/models/flux-1-schnell-fp8/text_to_image",
    "/image_generation/accounts/fireworks/models/flux-1-schnell-fp8",
]


def main() -> int:
    key = os.environ["FIREWORKS_API_KEY"]
    base = "https://api.fireworks.ai/inference/v1"
    for ep in ENDPOINTS:
        r = httpx.post(
            base + ep,
            headers={"Authorization": f"Bearer {key}", "Accept": "image/png"},
            json={"prompt": PROMPT, "aspect_ratio": "16:9",
                  "guidance_scale": 3.5, "num_inference_steps": 4},
            timeout=120,
        )
        print(f"{ep} -> {r.status_code} ({r.headers.get('content-type')})", file=sys.stderr)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            os.makedirs("assets", exist_ok=True)
            with open("assets/cover.png", "wb") as f:
                f.write(r.content)
            print(f"saved assets/cover.png ({len(r.content)//1024} KB)")
            return 0
    print("FAIL: no endpoint produced an image")
    return 1


if __name__ == "__main__":
    sys.exit(main())
