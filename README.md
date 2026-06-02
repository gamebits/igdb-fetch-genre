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
* **Input Spreadsheet Filename:** `Retro Master List - Sheet1.csv`
* **Python Script Filename:** `fetch_genres.py`
* **Generated Output Spreadsheet:** `Retro Master List - With Genres.csv` *(This file is automatically created during execution)*

### Expected & Acceptable Spreadsheet Layouts

The utility dynamically detects the shape of your CSV file and alters its parsing rules based on two acceptable formats:

#### Layout A: Multi-Column List (With Episode Filtering)
If your CSV contains multiple columns and specifically includes a column titled `Episode #`, the script activates its filtering engine. It will **only query IGDB for rows that have a valid episode number assigned**. Any rows with a blank, `-`, or missing `Episode #` column are skipped to protect API limits.
* **Genre Insertion:** Because the spreadsheet has three or more columns, the new `Genre` column is cleanly injected as the **fourth column** (between `Original System` and `Episode #`) to preserve the layout of your trailing columns.

#### Layout B: Thin/Single-Column List (Full Bulk Query)
If your CSV is stripped down (e.g., a simple list of raw game titles with fewer than three columns total) or lacks an `Episode #` column entirely, the filtering logic automatically turns off. The script will **bulk query and fetch genres for every single game title listed in the sheet**.
* **Genre Insertion:** Because the spreadsheet lacks the padding of a full list, the new `Genre` column is safely appended as the **very last column** of the file.

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