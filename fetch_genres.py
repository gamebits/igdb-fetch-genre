#!/usr/bin/env python3
import csv
import os
import sys
import time
from difflib import SequenceMatcher
import requests

# --- Configuration ---
CLIENT_ID = os.environ.get("IGDB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("IGDB_CLIENT_SECRET")

missing_vars = []
if not CLIENT_ID:
    missing_vars.append("IGDB_CLIENT_ID")
if not CLIENT_SECRET:
    missing_vars.append("IGDB_CLIENT_SECRET")

if missing_vars:
    print(f"Error: Please set the following environment variable(s): {', '.join(missing_vars)}.")
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

# Initialize highly granular multi-variable metrics engine
count_not_found = 0
count_total_successfully_updated_rows = 0
count_skipped_no_episode = 0

genres_updated = 0
genres_no_data = 0
genres_missing_index = 0
genres_skipped = 0

publishers_updated = 0
publishers_no_data = 0
publishers_missing_index = 0
publishers_skipped = 0

developers_updated = 0
developers_no_data = 0
developers_missing_index = 0
developers_skipped = 0

dates_updated = 0
dates_no_data = 0
dates_missing_index = 0
dates_skipped = 0

with open(INPUT_CSV, mode='r', encoding='utf-8-sig') as infile:
    first_line = infile.readline()
    has_title_line = "Title" not in first_line
    infile.seek(0)

    if has_title_line:
        title_line = infile.readline()

    reader = csv.DictReader(infile)
    # Clean up hidden header artifacts cleanly right at the moment fieldnames are parsed
    fieldnames = [f.replace("\xef\xbb\xbf", "").strip() for f in reader.fieldnames] if reader.fieldnames else []

    # --- METADATA HEADER DETECTOR PASS ---
    has_genre_col = any(f.lower() == "genre" for f in fieldnames)
    has_release_date_col = any(f.lower() == "release date" for f in fieldnames)
    has_publisher_col = any(f.lower() == "publisher" for f in fieldnames)
    has_developer_col = any(f.lower() == "developer" for f in fieldnames)

    # Resolve literal column field names as they exist exactly inside the source document
    genre_key = next((f for f in fieldnames if f.lower() == "genre"), "Genre")
    date_key = next((f for f in fieldnames if f.lower() == "date"), "Date")
    system_key = next((f for f in fieldnames if f.lower() == "original system"), "Original System")

    # Interchangeable filter alignment lookup: dynamically pair either 'Episode' or 'Episode #' variations
    episode_key = next((f for f in fieldnames if f.lower() in ("episode #", "episode")), "Episode #")

    pub_key = next((f for f in fieldnames if f.lower() == "publisher"), "Publisher")
    dev_key = next((f for f in fieldnames if f.lower() == "developer"), "Developer")
    rel_date_key = next((f for f in fieldnames if f.lower() == "release date"), "Release Date")

    detected_targets = []
    if has_genre_col: detected_targets.append("Genre")
    if has_release_date_col: detected_targets.append("Release Date")
    if has_publisher_col: detected_targets.append("Publisher")
    if has_developer_col: detected_targets.append("Developer")

    # Dynamic Column Injection Rule: Add Genre ONLY if ALL target columns are missing
    if not detected_targets:
        print("\nℹ️ No metadata headers (Genre, Release Date, Publisher, Developer) found.")
        print("Defaulting to Genre-only extraction.")
        confirm = input("Proceed with adding a Genre column? [Y/n]: ").strip().lower()
        if confirm in ('n', 'no'):
            print("Operation aborted by user.")
            sys.exit(0)
        has_genre_col = True
        detected_targets.append("Genre")
    else:
        print(f"\n📋 Detected metadata columns: {', '.join(detected_targets)}")
        confirm = input("Proceed with filling missing fields for these columns? [Y/n]: ").strip().lower()
        if confirm in ('n', 'no'):
            print("Operation aborted by user.")
            sys.exit(0)

    # Prompt user for episode filtering configuration if column is present (defaults to Yes)
    has_episode_column = episode_key in fieldnames
    filter_by_episode = True
    if has_episode_column:
        episode_confirm = input("Process only existing episodes? [Y/n]: ").strip().lower()
        if episode_confirm in ('n', 'no'):
            filter_by_episode = False

    # Final prompt offering a dry-run alternative right before operations begin
    dry_run_confirm = input("Perform a dry run? (Stream updates but do not write to file) [y/N]: ").strip().lower()
    is_dry_run = dry_run_confirm in ('y', 'yes')

    # # 3. Guard against accidental file destruction by prompting for overwrite confirmation
    # Executed ONLY if this instance intends to overwrite or commit new binary layout blocks to local paths
    if not is_dry_run and os.path.exists(OUTPUT_CSV):
        overwrite = input(f"⚠️ Warning: '{OUTPUT_CSV}' already exists. Overwrite? [y/N]: ").strip().lower()
        if overwrite not in ('y', 'yes'):
            print("Operation cancelled. Exiting script.")
            sys.exit(0)

    output_fields = list(fieldnames)

    # Determine column insertion index dynamically if Genre column didn't explicitly exist
    if has_genre_col and genre_key not in output_fields:
        if episode_key in fieldnames:
            episode_index = fieldnames.index(episode_key)
            output_fields = fieldnames[:episode_index] + ["Genre"] + fieldnames[episode_index:]
        else:
            output_fields = fieldnames + ["Genre"]
        genre_key = "Genre"

    # Pre-calculate row list to establish accurate total tracking indices
    raw_rows_list = list(reader)
    rows_list = []

    # Context-aware pre-filtering loop step to lock incremental tallies exactly to the active scope
    for raw_row in raw_rows_list:
        # Clean all incoming row dictionary keys to remove BOM prefixes cleanly
        row = {k.replace("\xef\xbb\xbf", "").strip(): v for k, v in raw_row.items() if k is not None}

        if has_episode_column and filter_by_episode:
            episode = row.get(episode_key)
            if not episode or episode.strip() in ("", "-", "None"):
                count_skipped_no_episode += 1
                continue
        rows_list.append(row)

    total_games = len(rows_list)

    # Build optimized payload field string
    query_fields = ["name", "platforms.name", "release_dates.y"]
    if has_genre_col: query_fields.append("genres.name")
    if has_release_date_col: query_fields.append("first_release_date")
    if has_publisher_col or has_developer_col:
        query_fields.extend([
            "involved_companies.publisher",
            "involved_companies.developer",
            "involved_companies.company.name"
        ])
    fields_payload = ", ".join(query_fields)

    has_date_column = date_key in fieldnames
    has_system_column = system_key in fieldnames

    # Helper wrapper to conditionally handle file lifecycle execution safely
    class DummyWriter:
        def writerow(self, row): pass

    outfile = None
    writer = DummyWriter()

    if not is_dry_run:
        outfile = open(OUTPUT_CSV, mode='w', encoding='utf-8', newline='')
        writer = csv.DictWriter(outfile, fieldnames=output_fields, extrasaction='ignore')
        if has_title_line:
            outfile.write(title_line)
        writer.writeheader()

        # Phase 1: Write back out rows skipped by episode filter mechanics if actively performing mutations
        if has_episode_column and filter_by_episode:
            for raw_row in raw_rows_list:
                row = {k.replace("\xef\xbb\xbf", "").strip(): v for k, v in raw_row.items() if k is not None}
                episode = row.get(episode_key)
                if not episode or episode.strip() in ("", "-", "None"):
                    if has_genre_col and genre_key not in row:
                        row[genre_key] = ""
                    clean_row = {field: row.get(field, "") for field in output_fields}
                    writer.writerow(clean_row)

    try:
        print(f"\nProcessing video games and writing updates real-time...{' [DRY RUN MODE]' if is_dry_run else ''}")
        print("-" * 70)

        for index, row in enumerate(rows_list, start=1):
            # Dynamic lookup fallback for the title field
            title = None
            for key, val in row.items():
                if key and key.lower() == "title":
                    title = val
                    break

            year = row.get(date_key, "").strip() if has_date_column else ""
            system = row.get(system_key, "").strip() if has_system_column else ""

            if not title or title.strip() == "":
                clean_row = {field: row.get(field, "") for field in output_fields}
                writer.writerow(clean_row)
                continue

            # Ensure the row dictionary physically contains a tracking placeholder if Genre was dynamically injected
            if has_genre_col and genre_key not in row:
                row[genre_key] = ""

            # Determine column execution requirements to track skipped data fields
            needs_genre = has_genre_col and not row.get(genre_key, "").strip()
            needs_pub = has_publisher_col and not row.get(pub_key, "").strip()
            needs_dev = has_developer_col and not row.get(dev_key, "").strip()
            needs_date = has_release_date_col and not row.get(rel_date_key, "").strip()

            # Record individual tracking tallies for fields that are pre-populated
            if has_genre_col and not needs_genre: genres_skipped += 1
            if has_publisher_col and not needs_pub: publishers_skipped += 1
            if has_developer_col and not needs_dev: developers_skipped += 1
            if has_release_date_col and not needs_date: dates_skipped += 1

            # If no requested fields are missing, output the row to skipped logs and move on
            if has_genre_col or has_publisher_col or has_developer_col or has_release_date_col:
                if not (needs_genre or needs_pub or needs_dev or needs_date):
                    print()  # Empty line separator before skipped row entry
                    print(f"⏭️  ({index}/{total_games}) [Skipped] {title.strip()} (All requested metadata already populated)")
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
                body_exact_year = f'search "{search_title}"; fields {fields_payload}; where release_dates.y = {year}; limit 20;'
                candidates = query_igdb_with_retry(body_exact_year)
                match_type = f"Exact Year [{year}]"

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
                body_year = f'search "{search_title}"; fields {fields_payload}; where release_dates.y >= {min_year} & release_dates.y <= {max_year}; limit 20;'
                candidates = query_igdb_with_retry(body_year)
                match_type = f"Year Window [{min_year}-{max_year}]"

                # Validation Guard: Discard the window pool if the top search result lacks names similarity entirely
                if candidates:
                    top_cand_norm = normalize_string(candidates[0].get("name", ""))
                    top_ratio = SequenceMatcher(None, target_norm, top_cand_norm).ratio()
                    if top_ratio < 0.35 and target_norm not in top_cand_norm and top_cand_norm not in target_norm:
                        candidates = None

            # --- STAGE 2: Broad Search Fallback ---
            if not candidates:
                body_exact = f'search "{search_title}"; fields {fields_payload}; limit 20;'
                candidates = query_igdb_with_retry(body_exact)
                match_type = "Standard Search"

            # --- STAGE 3: Fuzzy Wildcard Fallback ---
            if not candidates:
                fuzzy_title = target_norm
                body_fuzzy = f'fields {fields_payload}; where name ~ *"{fuzzy_title}"*; limit 20;'
                candidates = query_igdb_with_retry(body_fuzzy)
                match_type = "Fuzzy"

            # --- STAGE 4: Best Candidate Evaluation Loop ---
            matched_game = None

            if candidates:
                allowed_platforms = [normalize_string(p) for p in expand_platform_aliases(system)] if system else []

                # Pass A: Exact text title matches with correct platforms
                if system:
                    for candidate in candidates:
                        cand_norm = normalize_string(candidate.get("name", ""))
                        if cand_norm == target_norm:
                            cand_platforms = candidate.get("platforms", [])
                            for plat in candidate.get("platforms", []):
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

                # --- METADATA EXTRACTION AND SAFE PRESERVATION INJECTION ---
                log_components = []
                row_had_active_updates = False

                # 1. Update Genre (Only if previously empty)
                if has_genre_col:
                    if needs_genre:
                        if "genres" in matched_game and matched_game["genres"]:
                            genres = [g["name"] for g in matched_game["genres"]]
                            row[genre_key] = ", ".join(genres)
                            genres_updated += 1
                            row_had_active_updates = True
                        else:
                            row[genre_key] = "No genre data available"
                            genres_no_data += 1
                        log_components.append(f"Genre: {row[genre_key]}")
                    else:
                        log_components.append(f"Genre: {row[genre_key]} (Skipped)")

                # 2. Update Publisher (Only if previously empty)
                if has_publisher_col:
                    if needs_pub:
                        publishers = []
                        if "involved_companies" in matched_game:
                            for ic in matched_game["involved_companies"]:
                                if ic.get("publisher") is True:
                                    name = ic.get("company", {}).get("name")
                                    if name: publishers.append(name)
                        if publishers:
                            row[pub_key] = ", ".join(publishers)
                            publishers_updated += 1
                            row_had_active_updates = True
                        else:
                            row[pub_key] = "Unknown"
                            publishers_no_data += 1
                        log_components.append(f"Publisher: {row[pub_key]}")
                    else:
                        log_components.append(f"Publisher: {row[pub_key]} (Skipped)")

                # 3. Update Developer (Only if previously empty)
                if has_developer_col:
                    if needs_dev:
                        developers = []
                        if "involved_companies" in matched_game:
                            for ic in matched_game["involved_companies"]:
                                if ic.get("developer") is True:
                                    name = ic.get("company", {}).get("name")
                                    if name: developers.append(name)
                        if developers:
                            row[dev_key] = ", ".join(developers)
                            developers_updated += 1
                            row_had_active_updates = True
                        else:
                            row[dev_key] = "Unknown"
                            developers_no_data += 1
                        log_components.append(f"Developer: {row[dev_key]}")
                    else:
                        log_components.append(f"Developer: {row[dev_key]} (Skipped)")

                # 4. Update Release Date (Only if previously empty)
                if has_release_date_col:
                    if needs_date:
                        raw_timestamp = matched_game.get("first_release_date")
                        if raw_timestamp:
                            row[rel_date_key] = time.strftime('%Y-%m-%d', time.gmtime(raw_timestamp))
                            dates_updated += 1
                            row_had_active_updates = True
                        else:
                            row[rel_date_key] = "Unknown"
                            dates_no_data += 1
                        log_components.append(f"Release Date: {row[rel_date_key]}")
                    else:
                        log_components.append(f"Release Date: {row[rel_date_key]} (Skipped)")

                if row_had_active_updates:
                    count_total_successfully_updated_rows += 1

                # Structured Two-Line Streaming Output with blank spacing breaks
                log_details = " | ".join(log_components)
                print()  # Empty line separator before active query printout
                print(f"🎮 ({index}/{total_games}) {game_title} [{match_type} Match: {matched_game['name']}]")
                print(f"➡️  [{log_details}]")

            else:
                print()  # Empty line separator before error query printout
                print(f"❌ ({index}/{total_games}) {game_title} ➡️  No Match found on IGDB")
                if has_genre_col and needs_genre:
                    row[genre_key] = "Unknown"
                    genres_missing_index += 1
                if has_publisher_col and needs_pub:
                    row[pub_key] = "Unknown"
                    publishers_missing_index += 1
                if has_developer_col and needs_dev:
                    row[dev_key] = "Unknown"
                    developers_missing_index += 1
                if has_release_date_col and needs_date:
                    row[rel_date_key] = "Unknown"
                    dates_missing_index += 1
                count_not_found += 1

            clean_row = {field: row.get(field, "") for field in output_fields}
            writer.writerow(clean_row)

            time.sleep(0.25)
    finally:
        if outfile:
            outfile.close()

print("-" * 70)
print(f"📊 Summary Metric Tallies:")

if has_genre_col:
    print(f"  • Genres updated: {genres_updated}")
    print(f"  • Games found with no genre context listed: {genres_no_data}")
    print(f"  • Genre requests missing entirely from IGDB index: {genres_missing_index}")
    print(f"  • Genre entries skipped (pre-populated): {genres_skipped}")

if has_publisher_col:
    print()  # Visual break between categories
    print(f"  • Publishers updated: {publishers_updated}")
    print(f"  • Games found with no publisher context listed: {publishers_no_data}")
    print(f"  • Publisher requests missing entirely from IGDB index: {publishers_missing_index}")
    print(f"  • Publisher entries skipped (pre-populated): {publishers_skipped}")

if has_developer_col:
    print()  # Visual break between categories
    print(f"  • Developers updated: {developers_updated}")
    print(f"  • Games found with no developer context listed: {developers_no_data}")
    print(f"  • Developer requests missing entirely from IGDB index: {developers_missing_index}")
    print(f"  • Developer entries skipped (pre-populated): {developers_skipped}")

if has_release_date_col:
    print()  # Visual break between categories
    print(f"  • Release Dates updated: {dates_updated}")
    print(f"  • Games found with no release date context listed: {dates_no_data}")
    print(f"  • Release Date requests missing entirely from IGDB index: {dates_missing_index}")
    print(f"  • Release Date entries skipped (pre-populated): {dates_skipped}")

print()  # Visual break before global error counts
print(f"  • Global titles completely missing from IGDB index: {count_not_found}")
if has_episode_column and filter_by_episode:
    print(f"  • Games skipped (no assigned episode number): {count_skipped_no_episode}")
print(f"  • Total games updated: {count_total_successfully_updated_rows} out of {total_games}")
print("-" * 70)

if is_dry_run:
    print("🏁 Dry run complete! No mutations or output files were written.")
else:
    print(f"🎉 Success! Results written directly into: {OUTPUT_CSV}")
