#!/usr/bin/env python3
import csv
import os
import sys
import time
import requests

# --- Configuration ---
CLIENT_ID = os.environ.get("IGDB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("IGDB_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Please set IGDB_CLIENT_ID and IGDB_CLIENT_SECRET environment variables.")
    sys.exit(1)

# --- Step 1: Prompt the User for Input File ---
INPUT_CSV = input("Enter the input CSV filename (e.g., KensGames.csv): ").strip()

if not os.path.exists(INPUT_CSV):
    print(f"Error: The file '{INPUT_CSV}' could not be found in the current directory.")
    sys.exit(1)

# Dynamically calculate the output filename based on the input name
file_base, file_ext = os.path.splitext(INPUT_CSV)
OUTPUT_CSV = f"{file_base}-Genres{file_ext}"

# --- Step 2: Authenticate with Twitch OAuth2 ---
print("Authenticating with Twitch OAuth2...")
auth_url = f"https://id.twitch.tv/oauth2/token?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=client_credentials"
try:
    auth_response = requests.post(auth_url)
    auth_response.raise_for_status()
    access_token = auth_response.json().get("access_token")
except Exception as e:
    print(f"Authentication failed: {e}")
    sys.exit(1)

headers = {
    "Client-ID": CLIENT_ID,
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json"
}

# Helper function to request IGDB with rate-limit protection
def query_igdb_with_retry(query_body, max_retries=5):
    delay = 1.0
    for attempt in range(max_retries):
        response = requests.post("https://api.igdb.com/v4/games", headers=headers, data=query_body)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print(f"⚠️ Rate limited (429). Backing off for {delay}s (Attempt {attempt+1}/{max_retries})...")
            time.sleep(delay)
            delay *= 2
        else:
            print(f"⚠️ HTTP Error {response.status_code}")
            return None
    print("❌ Max retries reached for rate limiting.")
    return None

# --- Step 3: Stream, Filter, Query, and Write Rows ---
print(f"Opening {INPUT_CSV} for processing...")

with open(INPUT_CSV, mode='r', encoding='utf-8-sig') as infile:
    first_line = infile.readline()
    has_title_line = "Title" not in first_line
    infile.seek(0)
    
    if has_title_line:
        title_line = infile.readline()
        
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames if reader.fieldnames else []
    
    # Determine column insertion index dynamically
    if "Genre" not in fieldnames:
        if "Episode #" in fieldnames:
            episode_index = fieldnames.index("Episode #")
            output_fields = fieldnames[:episode_index] + ["Genre"] + fieldnames[episode_index:]
        elif len(fieldnames) >= 3:
            output_fields = fieldnames[:3] + ["Genre"] + fieldnames[3:]
        else:
            output_fields = fieldnames + ["Genre"]
    else:
        output_fields = fieldnames

    has_episode_column = "Episode #" in fieldnames

    with open(OUTPUT_CSV, mode='w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=output_fields)
        
        if has_title_line:
            outfile.write(title_line)
            
        writer.writeheader()
        
        print("Processing video games and writing updates real-time...")
        print("-" * 65)

        for row in reader:
            title = row.get("Title")
            
            if not title or title.strip() == "":
                row["Genre"] = ""
                writer.writerow(row)
                continue
            
            if has_episode_column:
                episode = row.get("Episode #")
                if not episode or episode.strip() in ("", "-", "None"):
                    row["Genre"] = ""
                    writer.writerow(row)
                    continue
            
            game_title = title.strip()
            body = f'search "{game_title}"; fields name, genres.name; limit 1;'
            
            data = query_igdb_with_retry(body)
            genre_str = ""
            
            if data:
                matched_game = data[0]
                if "genres" in matched_game:
                    genres = [g["name"] for g in matched_game["genres"]]
                    genre_str = ", ".join(genres)
                    print(f"🎮 {game_title} ➡️  [{genre_str}]")
                else:
                    genre_str = "No genre data available"
                    print(f"🎮 {game_title} ➡️  [No genre found]")
            else:
                print(f"❌ {game_title} ➡️  No Match found on IGDB")
                genre_str = "Unknown"
            
            row["Genre"] = genre_str
            writer.writerow(row)

            time.sleep(0.25)

print("-" * 65)
print(f"🎉 Success! Results written directly into: {OUTPUT_CSV}")