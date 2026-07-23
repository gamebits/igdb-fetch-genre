# IGDB Game Genre Fetcher Utility

Enrich a game collection CSV (or Trello board JSON export) with metadata from the **IGDB API**. The script matches titles, then writes release date, publisher, developer, platform, genre, and IGDB ID into an output CSV.

It was built for the [_New Game Plus_](https://ngppodcast.com/) podcast's [Retro Master List](https://bit.ly/RetroML), but you can use it with any compatible spreadsheet.

## Table of Contents

- [Prerequisites](#prerequisites)
- [1. Set Up Your IGDB API Account](#1-set-up-your-igdb-api-account)
- [2. Prepare Your Files](#2-prepare-your-files)
  - [Overwrite safeguard](#overwrite-safeguard)
  - [CSV spreadsheet layouts](#csv-spreadsheet-layouts)
  - [Trello board JSON exports](#trello-board-json-exports)
  - [How Date and Original System improve matching](#how-date-and-original-system-improve-matching)
- [3. Install and Prepare the Script](#3-install-and-prepare-the-script)
- [4. Set Credentials and Run](#4-set-credentials-and-run)
  - [Post-run triage (optional)](#post-run-triage-optional)
  - [Dry run](#dry-run)
  - [Placeholder refresh (optional)](#placeholder-refresh-optional)
  - [Release year drift validation](#release-year-drift-validation)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before you start, make sure you have:

| Requirement | Notes |
|---|---|
| **Terminal** | Any shell works. Examples in this guide use `zsh`. |
| **Python 3** | A local Python 3.x install. |
| **`requests` library** | Install from **`requirements.txt`** in [section 3](#3-install-and-prepare-the-script). |
| **Twitch developer app** | Free Client ID and Client Secret from the Twitch Developer Console (see [section 1](#1-set-up-your-igdb-api-account)). |
| **Input file** | A CSV with a `Title` column, or a Trello board JSON export. |

---

## 1. Set Up Your IGDB API Account

IGDB access goes through the **Twitch Developer Console**. Personal and non-commercial use is free.

1. Create or sign in to a [Twitch](https://www.twitch.tv/) account.
2. Enable **Two-Factor Authentication (2FA)** under your account's **Security and Privacy Settings**. Twitch requires 2FA for developer tools.
3. Open the [Twitch Developer Console](https://dev.twitch.tv/console/apps) and sign in.
4. Click **Register Your Application** and fill in:
   - **Name:** A unique name (for example, `RetroMasterListParser-YourName`).
   - **OAuth Redirect URLs:** `http://localhost` (required placeholder; this script uses app credentials, not a browser redirect).
   - **Category:** **Application Integration**.
   - **Client Type:** **Confidential**.
5. Open your app and click **Manage**.
   - Copy the **Client ID**.
   - Click **New Secret**, then copy the **Client Secret** immediately. You cannot view it again later.

---

## 2. Prepare Your Files

Put **`fetch_genres.py`** and your input file in the **same folder**.

Suggested layout:

| Item | Example |
|---|---|
| Working folder | `~/Desktop/ngp/` (any path works) |
| Script | **`fetch_genres.py`** |
| Input | **`Games.csv`** or **`trello.json`** |
| Output | Auto-named with `-Genres` (for example, **`Games-Genres.csv`**) |

When the script starts, it asks for the input filename:

- Press Enter to use the default: **`Games.csv`**.
- Type a name without an extension (for example, `Games` or `trello`). If that exact file is missing, the script tries `.csv`, then `.json`.
- Trello JSON inputs always write CSV output (for example, **`trello.json`** → **`trello-Genres.csv`**).

### Overwrite safeguard

If the output file already exists, the script asks before replacing it:

```text
⚠️ Warning: 'Games-Genres.csv' already exists. Overwrite? [y/N]:
```

Press Enter or type `n` to cancel without changing any files.

### CSV spreadsheet layouts

The script detects columns from your headers. You do not need a fixed schema.

#### Metadata columns the script can fill

It looks for: **`Genre`**, **`Publisher`**, **`Developer`**, **`Release Date`**, **`Platform`** / **`Original Platform`**, and **`IGDB ID`**.

- If any of those headers exist, the script lists them and asks you to confirm before querying IGDB.
- If none exist (or you use a Trello export), it asks which fields to fetch:

```text
Which metadata should be fetched from IGDB?
  [G]enre  [P]ublisher  [D]eveloper  [R]elease Date  [L] platform  [I] IGDB ID
  Enter one or more choices (e.g., GPD or all)
Your selection [g]:
```

What to enter:

- Press Enter for the default (**Genre** only).
- Type `all` for every field.
- Or combine letters such as `GPD` or `GI`.

The script adds blank columns for each selected field. **`IGDB ID`** stores the numeric IGDB game ID (for example, `7346` for *The Legend of Zelda: Breath of the Wild*).

#### Episode filtering

If your sheet has an **`Episode`** or **`Episode #`** column, the script asks:

```text
Process only existing episodes? [Y/n]:
```

| Choice | What happens |
|---|---|
| Enter / `y` / `yes` (default) | Process only rows with an episode value. Blank, `-`, and `None` rows are copied through without API calls. |
| `n` / `no` | Process every row. |

### Trello board JSON exports

You can point the script at a standard Trello board JSON export (for example, **`trello.json`**).

#### Export from Trello

1. Open your Trello board.
2. Open the board menu and choose **Print, Export, and Share** → **Export as JSON**.
3. Save the file next to **`fetch_genres.py`**.

#### How Trello cards map to columns

Each card becomes one row:

| Output column | Trello source |
|---|---|
| `Title` | Card name |
| `Release Date` | Custom field named **Release date** (if present), as `YYYY-MM-DD` |
| `Date` | Four-digit year from the release date (used for IGDB year filters) |
| `Original System` | Platform labels on the card, joined with ` / ` when multiple apply |

`Date` drives year-scoped IGDB searches. If `Date` already has a valid year, it takes precedence over extracting a year from `Release Date`. Blank `Release Date` cells are filled from IGDB when a match is found, even if you did not select Release Date in the metadata prompt.

#### Trello labels

Every board label becomes its own output column. Applied labels store the label name; otherwise the cell stays blank.

Platform-style labels (for example `Switch`, `Steam`, `PS4`) are also copied into **`Original System`** for matching. Status labels such as `Unreleased` and `Collection` stay in their label columns but are excluded from **`Original System`**.

**Example:** A card named *Prince of Persia: The Lost Crown* with **Release date** January 18, 2024 and a `Switch` label becomes:

- `Title`: Prince of Persia: The Lost Crown
- `Release Date`: 2024-01-18
- `Date`: 2024
- `Original System`: Switch
- `Switch` label column: Switch

Trello runs always show the metadata selection prompt (default: Genre only). Existing `Release Date`, `Date`, and `Original System` values still narrow IGDB searches. The output includes the metadata columns you chose plus all original label columns.

### How Date and Original System improve matching

Optional columns help avoid false matches (for example, a retro title vs. a modern remake).

#### `Date` column (search filter)

| Situation | Behavior |
|---|---|
| Valid 4-digit year (for example, `1994`) | Exact-year search first, then a ±1 year window if needed. |
| Missing or blank | Broad title search across all years. |

#### `Original System` column (platform tie-breaker)

| Situation | Behavior |
|---|---|
| Present (for example, `NES`, `GENESIS`) | Expands aliases (such as NES → Nintendo Entertainment System) and prefers candidates on that platform. Release metadata uses IGDB's per-platform release dates when available (for example, *Legend of Grimrock* on Switch uses the 2024 Switch date, not the 2012 PC debut). |
| Missing or blank | Relies on title similarity only, which can increase naming collisions. |

---

## 3. Install and Prepare the Script

1. Open a terminal and go to your working folder:

   ```zsh
   # Move into the folder that contains fetch_genres.py and your input file
   cd ~/Desktop/ngp/
   ```

2. Make the script executable:

   ```zsh
   # Allow running the script as an executable file
   chmod +x fetch_genres.py
   ```

3. Install Python dependencies:

   ```zsh
   # Install the requests library listed in requirements.txt
   pip install -r requirements.txt
   ```

---

## 4. Set Credentials and Run

The script reads your Twitch credentials from environment variables so you do not store secrets in code files.

```zsh
# Load your Twitch developer credentials for this terminal session
export IGDB_CLIENT_ID="your_actual_client_id_here"
export IGDB_CLIENT_SECRET="your_actual_client_secret_here"

# Start the enrichment script (it will prompt for the input file and options)
python3 fetch_genres.py
```

### Post-run triage (optional)

Some titles match multiple IGDB entries. At startup, the script asks whether to review low-confidence matches (about 45%–85%):

```text
Manually confirm potential mismatches after the automated run? [Y]es (interactive), [L]ist mismatches, [N]o (skip) [y/l/N]:
```

| Choice | What happens |
|---|---|
| `y` / `yes` | After the run, pick the correct IGDB entry (or mark as unknown) for each flagged row. Overrides are written back to the output. |
| `l` / `list` | Print a read-only list of flagged matches and keep the automatic selections. |
| Enter / `n` / `no` (default) | Skip review and keep automatic matches. |

### Dry run

Before querying, the script can simulate a full run without writing files:

```text
Perform a dry run? (Stream updates but do not write to file) [y/N]:
```

| Choice | What happens |
|---|---|
| `y` / `yes` | Runs matching and prints progress and summary metrics. Does not create or overwrite output files. |
| Enter / `n` / `no` (default) | Writes results to the output CSV (after overwrite confirmation if needed). |

### Placeholder refresh (optional)

After the triage prompt, you can re-query cells that contain script placeholders:

```text
Re-query rows with placeholder values (Unknown / No genre data available)? [y/N]:
```

| Choice | What happens |
|---|---|
| Enter / `n` / `no` (default) | Fill blank cells only. Non-empty cells (including `Unknown` and `No genre data available`) are skipped. |
| `y` / `yes` | Treat `Unknown` and `No genre data available` as eligible for a new lookup. Real user data is never overwritten. If IGDB returns better data, the placeholder is upgraded; otherwise it stays. |

### Release year drift validation

If your sheet has a **`Date`** column and the run populates **`Release Date`** from IGDB, the script compares your recorded year with IGDB's year.

When they differ, the summary includes a count such as:

```text
  • Games whose originally recorded release years were inaccurate: 2
```

If that count is greater than zero, a detail list follows:

```text
📋 Detailed List of Inaccurate Spreadsheet Release Years:
-----------------------------------------------------------------
🗓️  Color a Dinosaur (NES) — Recorded: 1993 vs. IGDB: 1994
🗓️  Chronicles of Mystara (PC) — Recorded: 2013 vs. IGDB: 2014
-----------------------------------------------------------------
```

---

## Troubleshooting

| Problem | What to try |
|---|---|
| `Error: Please set the following environment variable(s): …` | Export **`IGDB_CLIENT_ID`** and **`IGDB_CLIENT_SECRET`** in the same terminal session before running the script. |
| `Authentication failed` or missing access token | Confirm your Client ID and Client Secret are correct, then generate a new secret in the Twitch Developer Console if needed. Make sure 2FA is enabled on the Twitch account. |
| `The file '…' could not be found` | Place the input file in the same folder as **`fetch_genres.py`**, or type the correct name (with or without `.csv` / `.json`). |
| `JSON file does not appear to be a Trello board export` | Use a full board JSON export that includes `cards` and `labels`, not a single-card or unrelated JSON file. |
| Many wrong matches or `Unknown` results | Provide **`Date`** and **`Original System`** when possible, enable triage for low-confidence rows, or re-run with placeholder refresh after fixing titles. |
| `Missing system dependency 'requests'` | Run `pip install -r requirements.txt` in your active Python environment. |
