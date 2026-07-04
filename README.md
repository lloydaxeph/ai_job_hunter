# 🤖 AI Job Hunter Agent

An AI agent that intelligently searches, matches, and automatically applies to jobs using LLMs and browser automation.

---

## ✨ Features

- 🔍 Automatically searches for relevant job postings
- 🧠 Uses LLMs to intelligently evaluate job matches
- 📄 Tailors applications based on your profile
- 🤖 Automatically applies to supported job platforms using browser automation
- ⚙️ Fully configurable through a single `config.yaml` file
- 💾 Stores job postings, application history, and cached data using SQLite

---

## 🛠️ Tech Stack

- Python
- OpenAI API
- Playwright
- SQLite
- BeautifulSoup
- YAML

---

## 📋 Requirements

Before running the project, make sure you have:

- Python 3.10 or newer
- SQLite 3 (included with most Python installations)
- Git
- A valid OpenAI API key

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/lloydaxeph/ai_job_hunter.git
cd ai_job_hunter
```

### 2. Add your resumes

Place all of your resume files inside the **`Resumes/`** directory.

Example:

```text
Resumes/
├── Software_Resume.pdf
├── AI_Resume.pdf
└── Mechanical_Resume.pdf
```

Then reference these files in `config.yaml`.

### 3. Configure the application

Edit `config.yaml` to match your preferences, including:

- Search preferences
- Resume routing
- Personal information
- Job preferences
- AI settings
- Browser automation settings

Make sure the resume filenames in `config.yaml` match the files you placed in the `Resumes/` folder.

### 4. Create a `.env` file

Create a `.env` file in the project's root directory with the following contents:

```env
# ─── API Keys ──────────────────────────────────────────────────────
OPENAI_API_KEY=your_key

# ─── LinkedIn Credentials (for Easy Apply) ─────────────────────────
LINKEDIN_EMAIL=your_credentials
LINKEDIN_USER=your_credentials
LINKEDIN_PASSWORD=your_credentials

# ─── JobStreet Credentials ─────────────────────────────────────────
JOBSTREET_EMAIL=your_credentials
JOBSTREET_PASSWORD=your_credentials

# ─── Flask Web Dashboard ───────────────────────────────────────────
FLASK_SECRET_KEY=your_credentials
DASHBOARD_PORT=your_credentials
```

> **Note:** Never commit your `.env` file or expose your API keys and account credentials. Ensure `.env` is included in your `.gitignore`.

### 5. Install the dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the agent

```bash
python JobAgent.py
```

---

## 🗄️ Database

This project uses **SQLite** as its local database.

SQLite is lightweight and requires **no additional installation or database server** for most users, as it is included with standard Python installations.

The database stores information such as:

- Job postings
- Match scores
- Application history
- Cached AI results

---

## 📁 Recommended `.gitignore`

```gitignore
.env
*.db
__pycache__/
*.pyc
```

---

## ⚠️ Disclaimer

This project is intended for educational and personal use. Users are responsible for reviewing their configuration and ensuring that automated job applications comply with the terms of service of the job platforms they use.