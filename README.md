# IGDB Game Genre Fetcher Utility

This utility reads a game collection list from a CSV spreadsheet or a **Trello board JSON export**, queries the **IGDB API** via the Twitch Developer Portal to match video game titles, extracts their metadata (release date, publisher, developer, platform, and genre), and logs everything to an updated CSV spreadsheet.

It was vibe-coded by Ken Gagne using Google Gemini for use with the _[New Game Plus](https://ngppodcast.com/)_ podcast's [Retro Master List](https://bit.ly/RetroML), but it can be adapted to any use case or CSV.

## Table of Contents

- [1. Terminal Prerequisites](#1-terminal-prerequisites)
- [2. Setting Up Your IGDB API Account](#2-setting-up-your-igdb-api-account)
- [3. File and Directory Layout](#3-file-and-directory-layout)
  - [Overwrite Safeguard](#overwrite-safeguard)
  - [Expected & Acceptable Spreadsheet Layouts](#expected--acceptable-spreadsheet-layouts)
  - [Trello Board JSON Exports](#trello-board-json-exports)
  - [Metadata Detection & Query Precision](#metadata-detection--query-precision)
- [4. Preparing the Executable Utility](#4-preparing-the-executable-utility)
- [5. Injecting Credentials & Running the Script](#5-injecting-credentials--running-the-script)
  - [Smart Post-Run Triage Engine (Optional)](#smart-post-run-triage-engine-optional)
  - [Non-Destructive Exploration: The Dry Run Feature](#non-destructive-exploration-the-dry-run-feature)
  - [Historical Timeline Drift Validation](#historical-timeline-drift-validation)

## 1. Terminal Prerequisites

Before running this utility, ensure that your local terminal environment has the following prerequisites configured (installation of these components is out of scope for this guide):

* **zsh shell:** A functional Terminal instance running the standard `zsh` shell binary.
* **Python 3:** An accessible local installation of Python (v3.x).
* **Python dependencies:** The `requests` library, installable from the included `requirements.txt` (see section 3).

---

## 2. Setting Up Your IGDB API Account

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

## 3. File and Directory Layout

For the script to work flawlessly without manual path overrides, save the processing script and your target master list spreadsheet **in the exact same folder**.

Use the following naming layout:

* **Target Directory Location:** `~/Desktop/ngp/` *(or any folder path of your choice)*
* **Input Spreadsheet Filename:** The script prompts the user at execution time to identify the input file. If no name is typed and you press Enter, it automatically defaults to `Games.csv`. If you type a filename without an extension (e.g., `Games` or `trello`) and it doesn't exist, the script will automatically try `.csv` and `.json` extensions before throwing an error.
* **Python Script Filename:** `fetch_genres.py`
* **Generated Output Spreadsheet:** Dynamically named based on your input with `-Genres` appended (e.g., `Games-Genres.csv`, `trello-Genres.csv`, or `outliers-Genres.csv`). Trello JSON inputs always write CSV output. This file is automatically created during execution.

### Overwrite Safeguard
If the script detects that the output file (e.g., `Games-Genres.csv`) already exists in the folder, it will pause and prompt for explicit permission before overwriting anything:

```
⚠️ Warning: 'Games-Genres.csv' already exists. Overwrite? [y/N]:
```

If you decline or press Enter, the operation cancels cleanly without losing data.

### Expected & Acceptable Spreadsheet Layouts

The utility features an **Implicit Schema ("Detect and Inject")** workflow. Rather than requiring a static or rigid table setup, it dynamically alters its behavior based on which specific column headers it finds inside your sheet:

#### Found Targets: Explicit Metadata Columns
The script actively scans your spreadsheet headers for the presence of columns titled `Release Date`, `Platform`, `Publisher`, `Developer`, and `Genre`. 

* **Target Enrichment:** If any combination of these columns is found, the script flags them as active targets. At startup, it displays the discovered structure and prompts for explicit processing confirmation before querying the API.
* **Interactive Metadata Selection:** If the input is a Trello JSON export, or if a CSV has no `Genre`, `Publisher`, `Developer`, `Release Date`, or `Platform` / `Original Platform` columns, the script prompts you to choose which metadata to fetch from IGDB:

```text
Which metadata should be fetched from IGDB?
  [G]enre  [P]ublisher  [D]eveloper  [R]elease Date  [L] platform
  Enter one or more choices (e.g., GPD or all)
Your selection [g]:
```

Press Enter to accept the default (`Genre` only), type `all` for every field, or enter any combination of `G`, `P`, `D`, `R`, and `L`. Blank columns are added to the output for each selected field.

#### Episode Tracking & Interactive Filtering
If the spreadsheet contains either an `Episode` or `Episode #` column, the script automatically enables an interactive workflow configuration choice at startup:

* **Interactive Scope Filter Prompt:** The tool pauses and asks the operator: `Process only existing episodes? [Y/n]: `
* **Filtering Mode (Default / 'Yes'):** Pressing Enter or typing `y`/`yes` limits the script context exclusively to rows that have an active episode identifier. Rows without numbers (blank cells, `-`, or `None`) are cleanly bypassed during the lookup pass and written back out to the final document without using up API query limits. Under this mode, all real-time terminal progress indicators scale matching contexts directly to this subset (e.g., `(1/1)` rows instead of processing the entire sheet size).
* **Unrestricted Mode ('No'):** Submitting `n`/`no` deactivates the guard completely. The script processes every single entry in the list chronologically from top to bottom, regardless of whether an episode key is assigned.

### Trello Board JSON Exports

The utility also accepts a standard **Trello board JSON export** (the file produced when you export a board from Trello as JSON). Point the script at that file when prompted—for example, `trello.json`.

#### Exporting from Trello

1. Open your Trello board.
2. Open the board menu and choose **Print, Export, and Share** → **Export as JSON**.
3. Save the downloaded file alongside `fetch_genres.py`.

#### How Trello Cards Map to Spreadsheet Columns

Each Trello card becomes one row. The script derives search and metadata columns as follows:

| Output Column | Trello Source |
|---|---|
| `Title` | Card name |
| `Release Date` | Board custom field named **Release date** (if present), formatted as `YYYY-MM-DD` |
| `Date` | Four-digit year extracted from the release date (used for IGDB year-scoped searches) |
| `Original System` | Platform labels on the card (see below), joined with ` / ` when multiple apply |

The `Release Date` value is used to narrow IGDB searches: a full `YYYY-MM-DD` date has its four-digit year extracted automatically. If `Date` is also present, it takes precedence when it already contains a valid year. Blank `Release Date` cells are filled from IGDB whenever a match is found, even if you did not select Release Date in the metadata prompt.

#### Trello Labels

Every label defined on the board is preserved as its own column in the output CSV. If a card has a given label, that column contains the label name; otherwise the cell is left blank.

Platform-style labels (for example `Switch`, `Steam`, `PS4`) are also copied into `Original System` for IGDB matching. Status-style labels such as `Unreleased` and `Collection` are kept in their label columns but are excluded from `Original System`.

**Example:** A card named *Prince of Persia: The Lost Crown* with a **Release date** custom field of January 18, 2024 and a `Switch` label becomes:

* `Title`: Prince of Persia: The Lost Crown
* `Release Date`: 2024-01-18
* `Date`: 2024
* `Original System`: Switch
* `Switch` label column: Switch

When you run the script on a Trello JSON file, it always shows the metadata selection prompt above (default: Genre only). Trello's existing `Release Date`, `Date`, and `Original System` values are still used to narrow IGDB searches. Blank release dates are filled from IGDB results without requiring you to select Release Date in the prompt.

After IGDB enrichment, the output file includes the fetched metadata columns you chose alongside all original Trello label columns.

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

## 4. Preparing the Executable Utility

Before you execute the script for the first time, you must give your user profile file system permission to execute the Python script as a standalone system command.

1. Open your Terminal and switch directories into your target working folder:
    ```zsh
    cd ~/Desktop/ngp/
    ```
2. Modify the file system privileges to make the script file executable:
    ```zsh
    chmod +x fetch_genres.py
    ```
3. Install the Python dependencies from `requirements.txt`:
    ```zsh
    pip install -r requirements.txt
    ```

---

## 5. Injecting Credentials & Running the Script

To maximize safety and shield your private API tokens from being accidentally saved inside plain code files, the utility reads your IGDB details straight from your terminal's active system memory space. 

Run the following series of commands sequentially to define your parameters and launch your parsing script:

```zsh
# Step 1: Export your Twitch developer application keys to the local environment variables
export IGDB_CLIENT_ID="your_actual_client_id_here"
export IGDB_CLIENT_SECRET="your_actual_client_secret_here"

# Step 2: Execute the automation script
python3 fetch_genres.py
```

#### Smart Post-Run Triage Engine (Optional)
Some game titles might have multiple ambiguous matches; automatically selecting the best match might still produce the wrong result. The user can review and confirm these low-confidence (<=85% likelihood) matches at the end of the script.

At startup, right before data gathering kicks off, the script prompts you whether to track and review these potential outliers:

```text
Manually confirm potential mismatches after the automated run? [Y]es (interactive), [L]ist mismatches, [N]o (skip) [y/l/N]:
```

*   **Interactive Triage Mode (y / yes / Enter):** Launches a step-by-step terminal selection menu for each low-confidence match at the end of the run. You can inspect the spreadsheet asset details alongside up to five direct alternative listings pulled from the platform server to choose the exact entry or mark it invalid. Overrides chosen are permanently modified back into the spreadsheet rows.
    
*   **List Mismatches Mode (l / list):** A clean, read-only post-processing summary alternative. The script completely skips interactive confirmation checks and lists the total number of flagged items followed by a direct list of each row name, platform context, the automated database choice selection, and the computed matching confidence percentage (e.g., 🕹️ Lion King (Sega Genesis / SNES) matched with 'The Lion King' — 82% confident). The file is saved using the script's original autonomous selections.
    
*   **Autonomous Mode (n / no):** Bypasses all post-run evaluation loops entirely. The spreadsheet is output directly using the top automatic database matches without generating any lists or prompt overhead.

#### Non-Destructive Exploration: The Dry Run Feature
Right before the data retrieval pass initiates, the utility provides an interactive safeguard prompt offering a non-destructive verification mode:

```text
Perform a dry run? (Stream updates but do not write to file) [y/N]:
```

*   **Simulation Mode (y / yes):** If activated, the script executes all standard remote lookup logic, structural validation rules, and text similarity metrics. The entire two-line execution log streams to your terminal in real-time, and a complete breakdown of granular summary metrics is compiled at the end. However, **no changes are committed to disk, and no output CSV files are generated or overwritten**. This is ideal for checking API matching behaviors or testing rate limits safely.
    
*   **Standard Modification Mode (Default / Enter / n):** Bypasses the simulation. The script checks for local naming conflicts, prompts for overwrite confirmations if necessary, and permanently commits all recovered structural metadata directly into your newly generated output file.

#### Historical Timeline Drift Validation
If your source spreadsheet includes a standard `Date` column (the four-digit tracking year used to tighten API filters) *and* your execution environment is actively fetching and populating a `Release Date` metadata field from IGDB, the utility automatically monitors temporal timeline drift. 

During the execution cycle, the script cross-checks the four-digit string of your original `Date` cells against the year substring returned by the authoritative database server. If they differ, the metric engine logs the discrepancy.

At the very end of processing, a dedicated metric line prints out:
```text
  • Games whose originally recorded release years were inaccurate: 2
```

Whenever this counter is greater than zero, a detailed timeline validation block dynamically builds at the bottom of the log workspace, displaying a clean list of individual drift entries to simplify error tracking:

```text
📋 Detailed List of Inaccurate Spreadsheet Release Years:
-----------------------------------------------------------------
🗓️  Color a Dinosaur (NES) — Recorded: 1993 vs. IGDB: 1994
🗓️  Chronicles of Mystara (PC) — Recorded: 2013 vs. IGDB: 2014
-----------------------------------------------------------------
```
