#!/usr/bin/env python3
import csv
import os
import sys
import time
from difflib import SequenceMatcher
import requests

# --- Configuration ---
CLIENT_ID = os.environ.get("IGDB_CLIENT_ID")
# --- Configuration ---
CLIENT_ID = os.environ.get("IGDB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("IGDB_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Please set IGDB_CLIENT_ID and IGDB_CLIENT_SECRET environment variables.")
    sys.exit(1)

# --- Step 1: Prompt the User for Input File ---
INPUT_CSV = input("Enter the input CSV filename (e.g., Games.csv): ").strip()

# 1. Fall back to the default filename if the user hits Enter without typing
if not INPUT_CSV:
    INPUT_CSV = "Games.csv"

# 2. Automatically append .csv if the base name doesn't exist and lacks an extension
if not os.path.exists(INPUT_CSV):
    base, ext = os.path.splitext(INPUT_CSV)
    if not ext and os.path.exists(f"{INPUT_CSV}.csv"):
        INPUT_CSV = f"{INPUT_CSV}.csv"

if not os.path.exists(INPUT_CSV):
    print(f"Error: The file '{INPUT_CSV}' could not be found in the current directory.")
    sys.exit(1)

# Dynamically calculate the output filename based on the input name
file_base, file_ext = os.path.splitext(INPUT_CSV)
OUTPUT_CSV = f"{file_base}-Genres{file_ext}"

# 3. Guard against accidental file destruction by prompting for overwrite confirmation
if os.path.exists(OUTPUT_CSV):
    overwrite = input(f"⚠️ Warning: '{OUTPUT_CSV}' already exists. Overwrite? [y/N]: ").strip().lower()
    if overwrite not in ('y', 'yes'):
        print("Operation cancelled. Exiting script.")
        sys.exit(0)

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
    # Clean up common encoding artifacts before evaluating or searching strings
    text = text.replace("√©", "e").replace("‚Äôs", "s").replace("’", "").replace("'", "")
    text = text.replace("‚Äô", "s").replace("‚Äî", "")
    return "".join(c for c in text.lower() if c.isalnum())

# Helper function to match spreadsheet platform abbreviations to IGDB's naming conventions
def expand_platform_aliases(system_name):
    norm = system_name.upper().strip()
    mapping = {
        "NES": ["Nintendo Entertainment System"],
        "SNES": ["Super Nintendo Entertainment System", "Super Famicom"],
        "GENESIS": ["Sega Genesis", "Mega Drive"],
        "SEGA GENESIS": ["Sega Genesis", "Mega Drive"],
        "PC": ["PC (Microsoft Windows)", "Mac", "DOS"],
        "DOS": ["DOS", "PC (Microsoft Windows)"],
        "G&W": ["Game & Watch"],
        "GAME CUBE": ["GameCube"],
        "GAMECUBE": ["GameCube"],
        "MASTER SYSTEM": ["Sega Master System"],
        "SEGA MASTER SYSTEM": ["Sega Master System"]
    }
    return mapping.get(norm, [system_name])

# --- Step 3: Stream, Filter, Query, and Write Rows ---
print(f"Opening {INPUT_CSV} for processing...")

# Initialize summary metrics tallies
count_updated = 0
count_no_genre = 0
count_not_found = 0

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
    has_date_column = "Date" in fieldnames
    has_system_column = "Original System" in fieldnames

    with open(OUTPUT_CSV, mode='w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=output_fields, extrasaction='ignore')
        
        if has_title_line:
            outfile.write(title_line)
            
        writer.writeheader()
        
        print("Processing video games and writing updates real-time...")
        print("-" * 65)

        for row in reader:
            title = row.get("Title")
            year = row.get("Date", "").strip() if has_date_column else ""
            system = row.get("Original System", "").strip() if has_system_column else ""
            
            if not title or title.strip() == "":
                row["Genre"] = ""
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
            
            # Clean up raw text encoding artifacts entirely
            game_title = title.strip()
            search_title = game_title.replace("√©", "e").replace("‚Äôs", "'").replace("‚Äô", "'")
            target_norm = normalize_string(search_title)
            
            candidates = None
            match_type = "Search"
            
            # --- STAGE 1A: Exact Target Year Search ---
            # Prioritize an exact, precise year query match first to stop adjacent year companion title leakage
            if year and year.isdigit() and len(year) == 4:
                body_exact_year = f'search "{search_title}"; fields name, genres.name, platforms.name, release_dates.y; where release_dates.y = {year}; limit 20;'
                candidates = query_igdb_with_retry(body_exact_year)
                match_type = f"Exact Year ({year})"
                
                # Validation Guard: Reject the exact year candidate pool if the top search result is a false positive
                if candidates:
                    top_cand_norm = normalize_string(candidates[0].get("name", ""))
                    top_ratio = SequenceMatcher(None, target_norm, top_cand_norm).ratio()
                    if top_ratio < 0.35 and target_norm not in top_cand_norm and top_cand_norm not in target_norm:
                        candidates = None

            # --- STAGE 1B: Target Year Range Fallback Window (-1 / +1) ---
            # Run the wider 3-year range pool ONLY if the exact year filter comes up completely empty
            if not candidates and year and year.isdigit() and len(year) == 4:
                target_year = int(year)
                min_year = target_year - 1
                max_year = target_year + 1
                body_year = f'search "{search_title}"; fields name, genres.name, platforms.name, release_dates.y; where release_dates.y >= {min_year} & release_dates.y <= {max_year}; limit 20;'
                candidates = query_igdb_with_retry(body_year)
                match_type = f"Year Window ({min_year}-{max_year})"
                
                # Validation Guard: Discard the window pool if the top search result lacks names similarity entirely
                if candidates:
                    top_cand_norm = normalize_string(candidates[0].get("name", ""))
                    top_ratio = SequenceMatcher(None, target_norm, top_cand_norm).ratio()
                    if top_ratio < 0.35 and target_norm not in top_cand_norm and top_cand_norm not in target_norm:
                        candidates = None

            # --- STAGE 2: Broad Search Fallback ---
            if not candidates:
                body_exact = f'search "{search_title}"; fields name, genres.name, platforms.name; limit 20;'
                candidates = query_igdb_with_retry(body_exact)
                match_type = "Standard Search"
            
            # --- STAGE 3: Fuzzy Wildcard Fallback ---
            if not candidates:
                fuzzy_title = target_norm
                body_fuzzy = f'fields name, genres.name, platforms.name; where name ~ *"{fuzzy_title}"*; limit 20;'
                candidates = query_igdb_with_retry(body_fuzzy)
                match_type = "Fuzzy"
                
            # --- STAGE 4: Best Candidate Evaluation Loop ---
            matched_game = None
            genre_str = ""
            
            if candidates:
                allowed_platforms = [normalize_string(p) for p in expand_platform_aliases(system)] if system else []

                # Pass A: Exact text title matches with correct platforms
                if system:
                    for candidate in candidates:
                        cand_norm = normalize_string(candidate.get("name", ""))
                        if cand_norm == target_norm:
                            cand_platforms = candidate.get("platforms", [])
                            for plat in cand_platforms:
                                plat_norm = normalize_string(plat.get("name", ""))
                                if any(alias in plat_norm or plat_norm in alias for alias in allowed_platforms):
                                    matched_game = candidate
                                    break
                        if matched_game:
                            break

                # Pass B: Exact text title matches globally
                if not matched_game:
                    for candidate in candidates:
                        if normalize_string(candidate.get("name", "")) == target_norm:
                            matched_game = candidate
                            break

                # Pass C: Sequence Similarity Score + Correct Platforms (Whole word match validation)
                if not matched_game and system:
                    best_ratio = 0.0
                    for candidate in candidates:
                        cand_name = candidate.get("name", "")
                        cand_norm = normalize_string(cand_name)
                        ratio = SequenceMatcher(None, target_norm, cand_norm).ratio()
                        
                        # Strict whole word boundaries limit false-positive sequence matches
                        cand_words = cand_name.lower().replace(":", "").replace("-", "").split()
                        target_words = search_title.lower().replace(":", "").replace("-", "").split()
                        
                        is_valid_word_match = any(w in cand_words for w in target_words)
                        
                        if (target_norm in cand_norm or cand_norm in target_norm) and not matched_game:
                            ratio = max(ratio, 0.75)
                            
                        if is_valid_word_match and ratio > 0.50 and ratio > best_ratio:
                            cand_platforms = candidate.get("platforms", [])
                            for plat in cand_platforms:
                                plat_norm = normalize_string(plat.get("name", ""))
                                if any(alias in plat_norm or plat_norm in alias for alias in allowed_platforms):
                                    matched_game = candidate
                                    best_ratio = ratio
                                    break

                # Pass D: Global Sequence Similarity fallback with basic text word protection
                if not matched_game:
                    best_ratio = 0.0
                    for candidate in candidates:
                        cand_name = candidate.get("name", "")
                        cand_norm = normalize_string(cand_name)
                        ratio = SequenceMatcher(None, target_norm, cand_norm).ratio()
                        
                        cand_words = cand_name.lower().replace(":", "").replace("-", "").split()
                        target_words = search_title.lower().replace(":", "").replace("-", "").split()
                        is_valid_word_match = any(w in cand_words for w in target_words)
                        
                        if (target_norm in cand_norm or cand_norm in target_norm):
                            ratio = max(ratio, 0.75)
                        if is_valid_word_match and ratio > 0.50 and ratio > best_ratio:
                            matched_game = candidate
                            best_ratio = ratio
                
                # 3rd Priority: Default to first entry if strict filters exclude everything
                if not matched_game:
                    matched_game = candidates[0]
                
                # --- BLANK GENRE SAFEGUARD: Query global master record if specific variant is blank ---
                if matched_game and "genres" in matched_game and matched_game["genres"]:
                    genres = [g["name"] for g in matched_game["genres"]]
                    genre_str = ", ".join(genres)
                    print(f"🎮 {game_title} ➡️  [{genre_str}] ({match_type} Match: {matched_game['name']})")
                    count_updated += 1
                else:
                    genre_str = "No genre data available"
                    print(f"🎮 {game_title} ➡️  [No genre found via {match_type} Match]")
                    count_no_genre += 1
            else:
                print(f"❌ {game_title} ➡️  No Match found on IGDB")
                genre_str = "Unknown"
                count_not_found += 1
            
            row["Genre"] = genre_str
            clean_row = {field: row.get(field, "") for field in output_fields}
            writer.writerow(clean_row)

            time.sleep(0.25)

print("-" * 65)
print(f"📊 Summary Tally:")
print(f"  • Games updated: {count_updated}")
print(f"  • Games with no known genre: {count_no_genre}")
print(f"  • Games not found in the IGDB: {count_not_found}")
print("-" * 65)
print(f"🎉 Success! Results written directly into: {OUTPUT_CSV}")