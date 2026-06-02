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
* **Input Spreadsheet Filename:** The script prompts the user at execution time to identify the CSV file (e.g., `Games.csv` or `Retro Master List - Sheet1.csv`)
* **Python Script Filename:** `fetch_genres.py`
* **Generated Output Spreadsheet:** Dynamically named based on your input with `-Genres` appended (e.g., `Games-Genres.csv` or `Retro Master List - Sheet1-Genres.csv`) *(This file is automatically created during execution)*

### Expected & Acceptable Spreadsheet Layouts

The utility dynamically detects the shape of your CSV file and alters its parsing rules based on two acceptable formats:

#### Layout A: Multi-Column List (With Episode Filtering)
If your CSV contains multiple columns and specifically includes a column titled `Episode #`, the script activates its filtering engine. It will **only query IGDB for rows that have a valid episode number assigned**. Any rows with a blank, `-`, or missing `Episode #` column are skipped to protect API limits.
* **Genre Insertion:** Because the spreadsheet has three or more columns, the new `Genre` column is cleanly inserted as a new column immediately before the `Episode #` column, preserving the layout and content of the preceding and trailing columns.

#### Layout B: Thin/Single-Column List (Full Bulk Query)
If your CSV is stripped down (e.g., a simple list of raw game titles with fewer than three columns total) or lacks an `Episode #` column entirely, the filtering logic automatically turns off. The script will **bulk query and fetch genres for every single game title listed in the sheet**.
* **Genre Insertion:** Because the spreadsheet lacks the padding of a full list, the new `Genre` column is safely appended as the **very last column** of the file.

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