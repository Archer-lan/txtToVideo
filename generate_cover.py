import requests
import base64
import json

# SD WebUI API endpoint
url = "http://127.0.0.1:7860/sdapi/v1/txt2img"

# High impact, visually striking cover prompt
payload = {
    "prompt": "explosive dynamic composition, ten people in intense dramatic poses around a glowing magical circle, powerful magic energy swirling, a colossal terrifying goat-headed deity looming above with burning red eyes, thunder and lightning striking, epic cinematic lighting, vibrant saturated colors, hyper-detailed, masterpiece, mind-blowing visual, stunning spectacle, dramatic action scene, dynamic angle, powerful perspective, breathtaking, incredible details, award-winning illustration",
    "negative_prompt": "low quality, blurry, bad anatomy, extra limbs, deformed, watermark, text, simple, plain, dull colors, amateur, ugly, boring composition",
    "steps": 50,
    "width": 1280,
    "height": 720,
    "cfg_scale": 9,
    "sampler_name": "DPM++ 2M Karras",
    "hr_fix": True,
    "denoising_strength": 0.5
}

print("Generating high-impact cover image...")
response = requests.post(url, json=payload)

if response.status_code == 200:
    result = response.json()
    image_data = result['images'][0]

    # Decode and save
    with open(r"c:\Users\78125\Desktop\project\txtToVideo\workspace\十日终焉_第1-10章_封面.png", "wb") as f:
        f.write(base64.b64decode(image_data))

    print("High-impact cover image saved!")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
