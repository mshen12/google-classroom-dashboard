# Google Classroom Homework Dashboard — Setup Guide

## Prerequisites
- Python 3.8 or newer installed
- Your child must be signed into a Google account enrolled in Google Classroom

---

## Step 1: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** (top bar) → **New Project**
3. Name it something like `Homework Dashboard` and click **Create**
4. Make sure the new project is selected in the top bar

---

## Step 2: Enable the Google Classroom API

1. In the left menu, go to **APIs & Services → Library**
2. Search for **Google Classroom API**
3. Click on it and click **Enable**

---

## Step 3: Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. If prompted, click **Configure Consent Screen** first:
   - Choose **External** → **Create**
   - Fill in "App name" (e.g. `Homework Dashboard`) and your email
   - Click **Save and Continue** through all steps
   - On the **Test users** step, add the Google account your child uses for Classroom
   - Click **Back to Dashboard**
4. Back on Credentials, click **+ Create Credentials → OAuth client ID** again
5. For **Application type**, choose **Desktop app**
6. Name it anything (e.g. `Homework Dashboard`) and click **Create**
7. Click **Download JSON** on the confirmation dialog (or the download icon next to your credential)
8. **Rename the downloaded file to `credentials.json`** and place it in this folder

---

## Step 4: Install Dependencies

Open a terminal in this folder and run:

```bash
pip install -r requirements.txt
```

---

## Step 5: Run the Script

```bash
python fetch_assignments.py
```

- **First run:** A browser window will open asking you to sign in with your child's Google account and grant permission. This only happens once.
- **Subsequent runs:** It uses the saved token — no sign-in needed.

The script will generate `assignments.html` and open it automatically in your browser.

---

## Refreshing Assignments

Run the script any time to get fresh data:

```bash
python fetch_assignments.py
```

You can also create a desktop shortcut or batch file to make it easy for kids to run.

---

## Multiple Kids

If you have multiple children in different Google accounts, you can keep separate copies of this folder (one per child) with each child's own `credentials.json` and `token.json`.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `credentials.json not found` | Make sure the file is in the same folder as the script |
| `Access blocked: This app is not verified` | Click **Advanced → Go to Homework Dashboard (unsafe)** — this is normal for personal/test apps |
| `No active courses found` | Make sure the Google account is enrolled in active Classroom courses |
| Token errors | Delete `token.json` and re-run to re-authenticate |
