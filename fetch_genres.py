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
INPUT_CSV = input("Enter the input CSV filename (e.g., Games.csv): ").strip()

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

# Helper function to normalize text for logical matching evaluation
def normalize_string(text):
    if not text:
        return ""
    # Lowercase and strip common punctuation dividers to find near-perfect string pairs
    return "".join(c for c in text.lower() if c.isalnum())

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
        # Crucial: Restricting to extrasaction='ignore' prevents layout bleeding
        writer = csv.DictWriter(outfile, fieldnames=output_fields, extrasaction='ignore')
        
        if has_title_line:
            outfile.write(title_line)
            
        writer.writeheader()
        
        print("Processing video games and writing updates real-time...")
        print("-" * 65)

        for row in reader:
            title = row.get("Title")
            
            if not title or title.strip() == "":
                row["Genre"] = ""
                # Construct clean dictionary matching output formatting exactly
                clean_row = {field: row.get(field, "") for field in output_fields}
                writer.writerow(clean_row)
                continue
            
            if has_episode_column:
                episode = row.get("Episode #")
                if not episode or episode.strip() in ("", "-", "None"):
                    row["Genre"] = ""
                    clean_row = {field: row.get(field, "") for field in output_fields}
                    writer.writerow(clean_row)
                    continue
            
            game_title = title.strip()
            target_norm = normalize_string(game_title)
            
            # --- STAGE 1: Broad Exact/Search (Pulls up to 5 candidates) ---
            # By pulling a small list, we prevent random spin-offs from overriding the main entry
            body_exact = f'search "{game_title}"; fields name, genres.name; limit 5;'
            candidates = query_igdb_with_retry(body_exact)
            match_type = "Search Match"
            
            # --- STAGE 2: Fuzzy Wildcard Fallback (If Stage 1 returned completely empty) ---
            if not candidates:
                fuzzy_title = game_title.lower().replace(":", "").replace("-", "")
                body_fuzzy = f'fields name, genres.name; where name ~ *"{fuzzy_title}"*; limit 5;'
                candidates = query_igdb_with_retry(body_fuzzy)
                match_type = "Fuzzy Match"
                
            # --- STAGE 3: Best Candidate Selection Loop ---
            matched_game = None
            genre_str = ""
            
            if candidates:
                # Loop through candidates to find the closest alphanumeric match to your CSV name
                for candidate in candidates:
                    cand_norm = normalize_string(candidate.get("name", ""))
                    # If an exact normalized match is found, lock it in immediately
                    if cand_norm == target_norm or target_norm in cand_norm:
                        matched_game = candidate
                        break
                
                # Fallback safety: if no candidate fits perfectly, default cleanly to the first returned option
                if not matched_game:
                    matched_game = candidates[0]
                    
                if "genres" in matched_game:
                    genres = [g["name"] for g in matched_game["genres"]]
                    genre_str = ", ".join(genres)
                    print(f"🎮 {game_title} ➡️  [{genre_str}] ({match_type}: {matched_game['name']})")
                else:
                    genre_str = "No genre data available"
                    print(f"🎮 {game_title} ➡️  [No genre found via {match_type}]")
            else:
                print(f"❌ {game_title} ➡️  No Match found on IGDB")
                genre_str = "Unknown"
            
            row["Genre"] = genre_str
            # Construct clean dictionary matching output formatting exactly to fix column skewing
            clean_row = {field: row.get(field, "") for field in output_fields}
            writer.writerow(clean_row)

            time.sleep(0.25)

print("-" * 65)
print(f"🎉 Success! Results written directly into: {OUTPUT_CSV}")