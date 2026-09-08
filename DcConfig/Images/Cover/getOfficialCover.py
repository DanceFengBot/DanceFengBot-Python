import requests
import os
import json
from datetime import datetime
import time

# Ensure the ./config directory exists
os.makedirs('./OfficialImage', exist_ok=True)

payload = {}
headers = {}

# Record the start time
start_time = time.time()

for i in range(1, 31):
    for j in range(1, 151):
        url = f"https://dancedemo.shenghuayule.com/Dance/api/User/GetMusicRankingNew?musicIndex={j}&keyword=&page={i}&pagesize=15&machineRank=false&isStrict=false"
        response = requests.request("GET", url, headers=headers, data=payload)

        try:
            # Parse JSON response directly from the URL
            data = response.json()

            # Extract MusicID and Cover
            for item in data.get("List", []):
                music_id = item.get("MusicID")
                cover_url = item.get("Cover")

                if music_id and cover_url:
                    # Remove the "/200" suffix from the Cover URL
                    cover_url = cover_url.rsplit('/200', 1)[0]

                    try:
                        # Download the Cover image
                        cover_response = requests.get(cover_url, stream=True, timeout=30)
                        cover_response.raise_for_status()

                        # Save the image as {MusicID}.jpg
                        cover_path = os.path.join('./OfficialImage', f"{music_id}.jpg")
                        with open(cover_path, 'wb') as f:
                            for chunk in cover_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)

                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ Downloaded: {cover_path}")
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ Failed to download {cover_url}: {e}")
        except json.JSONDecodeError:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Failed to decode JSON response.")

# Record the end time
end_time = time.time()

# Output the total runtime
print(f"Total runtime: {end_time - start_time:.2f} seconds")