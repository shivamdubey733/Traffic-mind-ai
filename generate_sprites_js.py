import os
import base64

v_dir = r"C:\Users\Shivam dubey\Downloads\SHIVAM DUBEY\PROJECTS\TrafficMind_AI\static\images\vehicles"
out_js = r"C:\Users\Shivam dubey\Downloads\SHIVAM DUBEY\PROJECTS\TrafficMind_AI\static\js\vehicle_sprites.js"

os.makedirs(os.path.dirname(out_js), exist_ok=True)

mapping = {
    'car_blue': 'car_blue.svg',
    'car_red': 'car_red.svg',
    'car_silver': 'car_silver.svg',
    'car_yellow': 'car_yellow.svg',
    'car_suv': 'car_suv.svg',
    'bus': 'bus_transit.svg',
    'truck': 'truck_semi.svg',
    'ambulance': 'ambulance.svg',
    'motorcycle': 'motorcycle.svg'
}

js_lines = [
    "// TrafficMind AI - Pre-rendered Photorealistic Vehicle Vector Sprites",
    "window.VEHICLE_SPRITES = {};",
    ""
]

for key, fname in mapping.items():
    fpath = os.path.join(v_dir, fname)
    with open(fpath, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    data_url = f"data:image/svg+xml;base64,{b64}"
    js_lines.append(f"// Sprite: {key} ({fname})")
    js_lines.append(f"(function() {{")
    js_lines.append(f"    const img = new Image();")
    js_lines.append(f"    img.src = '{data_url}';")
    js_lines.append(f"    window.VEHICLE_SPRITES['{key}'] = img;")
    js_lines.append(f"}})();")
    js_lines.append("")

with open(out_js, 'w', encoding='utf-8') as f:
    f.write("\n".join(js_lines))

print("Successfully generated vehicle_sprites.js, size:", os.path.getsize(out_js), "bytes")
