# IGDB Game Genre Fetcher Utility

This utility reads a game collection list from a CSV spreadsheet, queries the **IGDB API** via the Twitch Developer Portal to match video game titles, extracts their official genres, and logs everything to an updated CSV spreadsheet.

It was vibe-coded by Ken Gagne using Google Gemini for use with the _[New Game Plus](https://ngppodcast.com/)_ podcast's [Retro Master List](https://bit.ly/RetroML), but it can be adapted to any use case or CSV.

## Terminal Prerequisites

Before running this utility, ensure that your local terminal environment has the following prerequisites configured (installation of these components is out of scope for this guide):

* **zsh shell:** A functional Terminal instance running the standard `zsh` shell binary.
* **Python 3:** An accessible local installation of Python (v3.x).
* **Requests module:** The Python `requests` library installed within your active Python workspace environment or local virtual environment.

---

## 1. Setting Up Your IGDB API Account

IGDB processes all public API integrations natively through the **Twitch Developer Console**. The endpoints are entirely free for personal and non-commercial application development.

1. **Twitch Account Setup:** Navigate to [Twitch](https://www.twitch.tv/) and sign up for a free standard user account (or log into an existing one).
2. **Enable Two-Factor Authentication (2FA):** Twitch requires 2FA to use developer toolsets. Access your account's **Security and Privacy Settings** and activate 2FA using an authenticator app or phone number.
3. **Access the Developer Portal:** Navigate to the [Twitch Developer Console](https://dev.twitch.tv/console/apps) and sign in using your Twitch credentials.
4. **Register Your Application:** Click the **Register Your Application** button on the console dashboard and fill out the fields exactly as follows:
    * **Name:** Choose a globally unique name (e.g., `RetroMasterListParser-YourName`).
    * **OAuth Redirect URLs:** Enter `http://localhost` (The utility uses internal application authentication, but this field requires a valid placeholder to save).
    * **Category:** Choose **Application Integration** from the dropdown menu.
    * **Client Type:** Select **Confidential**.
5. **Collect Your Credentials:** Locate your newly registered application profile in the dashboard list and click **Manage**.
    * Copy the string labeled **Client ID** and save it safely.
    * Click the **New Secret** button to generate an application password. Copy this **Client Secret** string immediately; it will disappear forever once you navigate away from the page.

---

## 2. File and Directory Layout

For the script to work flawlessly without manual path overrides, save the processing script and your target master list spreadsheet **in the exact same folder**.

Use the following naming layout:

* **Target Directory Location:** `~/Desktop/ngp/` *(or any folder path of your choice)*
* **Input Spreadsheet Filename:** The script prompts the user at execution time to identify the CSV file. If no name is typed and you press Enter, it automatically defaults to `Games.csv`. If you type a filename without an extension (e.g., `Games`) and it doesn't exist, the script will automatically append `.csv` and try to read it before throwing an error.
* **Python Script Filename:** `fetch_genres.py`
* **Generated Output Spreadsheet:** Dynamically named based on your input with `-Genres` appended (e.g., `Games-Genres.csv` or `outliers-Genres.csv`). This file is automatically created during execution.

### Overwrite Safeguard
If the script detects that the output file (e.g., `Games-Genres.csv`) already exists in the folder, it will pause and prompt for explicit permission before overwriting anything:

```
⚠️ Warning: 'Games-Genres.csv' already exists. Overwrite? [y/N]:
```

If you decline or press Enter, the operation cancels cleanly without losing data.

### Expected & Acceptable Spreadsheet Layouts

The utility features an **Implicit Schema ("Detect and Inject")** workflow. Rather than requiring a static or rigid table setup, it dynamically alters its behavior based on which specific column headers it finds inside your sheet:

#### Found Targets: Explicit Metadata Columns
The script actively scans your spreadsheet headers for the presence of `Genre`, `Release Date`, `Publisher`, and `Developer`. 

* **Target Enrichment:** If any combination of these columns is found, the script flags them as active targets. At startup, it displays the discovered structure and prompts for explicit processing confirmation before querying the API.
* **Selective Genre Column Injection:** If the `Genre` column is missing from your header row, it will **only** be dynamically added if all other metadata targets (`Publisher`, `Developer`, and `Release Date`) are also completely missing from the sheet. 

#### Episode Tracking & Interactive Filtering
If the spreadsheet contains either an `Episode #` or `Episode` column, the script automatically enables an interactive workflow configuration choice at startup:

* **Interactive Scope Filter Prompt:** The tool pauses and asks the operator: `Process only existing episodes? [Y/n]: `
* **Filtering Mode (Default / 'Yes'):** Pressing Enter or typing `y`/`yes` limits the script context exclusively to rows that have an active episode identifier. Rows without numbers (blank cells, `-`, or `None`) are cleanly bypassed during the lookup pass and written back out to the final document without using up API query limits. Under this mode, all real-time terminal progress indicators scale matching contexts directly to this subset (e.g., `(1/1)` rows instead of processing the entire sheet size).
* **Unrestricted Mode ('No'):** Submitting `n`/`no` deactivates the guard completely. The script processes every single entry in the list chronologically from top to bottom, regardless of whether an episode key is assigned.

#### Target Fallback: Failsafe Routine (Genre-Only Mode)
If your spreadsheet lacks all four primary metadata headers entirely (e.g., it is a simple list consisting exclusively of raw game titles), or explicitly requests only `Genre`, the utility automatically stabilizes the layout:

* **Default Extraction Alignment:** It operates in a **Genre-only** extraction mode and prompts you for validation before continuing. If a new `Genre` column needs to be created, the script checks your file for an `Episode #` or `Episode` column. If either variation is present, the new `Genre` column is cleanly injected immediately to its left. If no episode tracking column exists, it is safely appended as the very last column on the far right of your generated file.

---

### Metadata Detection & Query Precision

The utility detects and leverages optional metadata columns to drastically improve search accuracy and eliminate false positives (such as matching a retro game with a modern sequel or subtitle expansion). 

#### 1. "Date" Column (The Search Filter)
* **How it is used:** If a column named `Date` is present and contains a valid 4-digit year (e.g., `1994`), the script treats this as the primary chronological anchor. It will execute an initial **Exact Year Search** targeting only games released in that specific year. If no valid match is found, it automatically drops down to a **Year Window Fallback Search** checking a strict 3-year sliding window ($\pm 1$ year from the target date). 
* **If missing or blank:** The script skips chronological scoping entirely and bypasses the year-window validation guards. It falls back to a broad database text search, querying the title globally across all eras.

#### 2. "Original System" Column (The Tie-Breaker)
* **How it is used:** If a column named `Original System` is present, its content acts as the ultimate platform filter during candidate evaluation. The script runs the spreadsheet value through an internal alias translator (e.g., expanding `NES` to `"Nintendo Entertainment System"` or `GENESIS` to `"Sega Genesis"` or `"Mega Drive"`) and requires any matching candidate from the API to exist on that platform layout to pass strict evaluation passes.
* **If missing or blank:** Platform validation constraints are disabled. The script relies purely on text similarity scoring across global database records, which can increase the likelihood of naming collisions on highly common words or franchise names.

---

## 3. Preparing the Executable Utility

Before you execute the script for the first time, you must give your user profile file system permission to execute the Python script as a standalone system command.

1. Open your Terminal and switch directories into your target working folder:
    ```zsh
    cd ~/Desktop/ngp/
    ```
2. Modify the file system privileges to make the script file executable:
    ```zsh
    chmod +x fetch_genres.py
    ```

---

## 4. Injecting Credentials & Running the Script

To maximize safety and shield your private API tokens from being accidentally saved inside plain code files, the utility reads your IGDB details straight from your terminal's active system memory space. 

Run the following series of commands sequentially to define your parameters and launch your parsing script:

```zsh
# Step 1: Export your Twitch developer application keys to the local environment variables
export IGDB_CLIENT_ID="your_actual_client_id_here"
export IGDB_CLIENT_SECRET="your_actual_client_secret_here"

# Step 2: Execute the automation script
python3 fetch_genres.py