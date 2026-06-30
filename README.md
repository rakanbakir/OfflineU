# OfflineU: Self-Hosted Local Course Loader & Progress Tracker

**OfflineU** is a sleek, self-hosted web app designed to load and view your offline video, audio, text, and quiz-based training courses. Whether it's Udemy downloads, "open sourced" training archives, or personal content, OfflineU turns your course folder into a fully navigable dashboard with automatic progress tracking.

---

## ✨ Features

* 📁 **Dynamic folder parsing**: Scans and maps your course structure into a browsable tree view.
* � **Smart folder finder**: Automatically searches common locations (Downloads, Documents, Desktop) — use just the folder name!
* �🎥 **Video & Audio player**: Integrated media player with resume & completion tracking.
* 📄 **Text & HTML viewer**: Supports .txt, .md, .html, .pdf, and more.
* ✅ **Lesson progress tracking**: Auto-saves your time spent and marks lessons as completed.
* ♻️ **Continue where you left off**: Resume instantly from your last-accessed lesson.
* 💾 **Local-first & private**: 100% offline. No cloud, no tracking, no nonsense.
* 🧑‍💻 **Works with any course format**: No metadata required, just structured folders.
* 📊 **AI-powered lesson analysis**: Optional integration with OpenAI, Anthropic, Google Gemini, or local Ollama for automatic lesson summaries and analysis.
* 📝 **Comprehensive logging**: All activities are logged with date-based filenames for easy tracking and debugging.
* 🧠 **Ideal for hoarders, students, or offline learning setups**

---

## 🗈️ Screenshots

> ![image](https://github.com/WhiskeyCoder/OfflineU/blob/main/images/lesson-0-8-2025-08-04-04_58_17.png)

---

## 🛠️ Installation

### 🔁 Quick Start (Local)

1. Clone the repo:

   ```bash
   git clone https://github.com/WhiskeyCoder/OfflineU.git
   cd OfflineU
   ```

2. Install Python dependencies:

   ```bash
   pip install flask
   ```

3. Run the app:

   ```bash
   python offlineu_core.py --create-templates
   ```

4. Open your browser:

   ```
   http://127.0.0.1:5000
   ```

---

## 📖 How to Load a Course

### Option 1: Smart Folder Finder (Easiest) 🚀
1. Open the app at `http://localhost:5000`
2. Enter just the **folder name** (e.g., `My Course` or `Python Masterclass`)
3. Click **"Load Course"** or press Enter
4. OfflineU automatically searches: `~/Downloads`, `~/Documents`, `~/Desktop`, `~/Courses`

### Option 2: Browse Button
1. Click the **"Browse"** button
2. Select your course folder from the file picker
3. The course loads automatically

### Option 3: Full Path
1. Paste the complete path to your course folder
2. Click **"Load Course"**

---

## 📂 Folder Structure Example

```bash
MyCourse/
├── Section 1/
│   ├── 01 - Intro.mp4
│   ├── 02 - Setup Guide.pdf
│   └── 03 - Quiz.html
├── Section 2/
│   ├── 04 - Advanced Tips.mp4
│   └── resources/
│       └── extras.md
└── .offlineu_progress.db  ← created automatically
```

> 🌟 File types are detected automatically — videos, audio, quizzes, and docs.

---

## 📁 Supported File Types

| Type      | Extensions                                                  |
| --------- | ----------------------------------------------------------- |
| Videos    | `.mp4`, `.mkv`, `.webm`, `.mov`, `.avi`, etc.               |
| Audio     | `.mp3`, `.wav`, `.aac`, etc.                                |
| Docs      | `.txt`, `.md`, `.html`, `.pdf`, `.docx`                     |
| Subtitles | `.srt`, `.vtt`                                              |
| Quizzes   | Detected if file name contains `quiz`, `exam`, `test`, etc. |

---

## 🤖 AI-Powered Lesson Analysis (Optional)

OfflineU integrates with multiple AI providers to automatically analyze and summarize your lessons:

### Supported AI Providers

| Provider        | Models                                          | Setup                          |
| --------------- | ----------------------------------------------- | ------------------------------ |
| **OpenAI**      | GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5      | Requires API key               |
| **Anthropic**   | Claude Opus 4.5, Claude Sonnet, Claude Haiku    | Requires API key               |
| **Google**      | Gemini 1.5 Pro, Flash, 2.0 Flash               | Requires API key               |
| **Ollama**      | Local models (Llama, Mistral, Phi, etc.)        | No API key, runs locally       |
| **GitHub Copilot** | GPT-4o, Claude, O1, Gemini 2.0                 | Requires GitHub PAT            |

### Features

- 📋 Automatic lesson summaries
- 🔑 Key points extraction
- 📚 Topic identification
- 🎯 Difficulty level assessment
- ⚙️ Prerequisites detection
- 💡 Learning takeaways

### Usage

Use the `ai_analyzer.py` script to analyze lessons programmatically or integrate AI capabilities into your workflow.

---

## 📝 Logging

All activities are automatically logged to the `logs/` directory with **date-based filenames** for easy organization:

- **Log files**: `offlineu_YYYY-MM-DD.log` (e.g., `offlineu_2026-05-22.log`)
- **Automatic rotation**: Logs are rotated when they exceed 5MB
- **History retention**: Up to 10 backup log files are maintained
- **Format**: Each entry includes timestamp, log level, and message

Check logs to track:
- Application startup and errors
- Course loading activities
- Progress updates
- API calls and responses

---

- **Organize by chapters**: Create folders for each section or chapter for better navigation
- **Use descriptive names**: Prefix videos with numbers (e.g., `01 - Intro.mp4`, `02 - Setup.mp4`)
- **Mixed content**: Put videos, notes, and PDFs in the same folder — OfflineU handles all types
- **Progress saves automatically**: Your completion status and bookmarks are saved locally in `.offlineu_progress.db` (SQLite)
- **No internet needed**: Everything is processed locally — no uploads, no tracking

---

## ⚙️ CLI Options

| Option               | Description                     |
| -------------------- | ------------------------------- |
| `--host`             | Set host (default: `0.0.0.0`)   |
| `--port`             | Set port (default: `5000`)      |
| `--debug`            | Enable Flask debug mode         |
| `--create-templates` | Generate default HTML templates |
| `<course_path>`      | Load course directly at startup |

**Examples:**
```bash
# Run on custom port
python offlineu_core.py --port 8080

# Auto-load a course at startup
python offlineu_core.py "/Users/you/Courses/My Course"

# Debug mode
python offlineu_core.py --debug --port 5000
```

---

## 🧠 Roadmap

* [x] Base function and testing
* [ ] Multi-user profile support
* [ ] Dark/light theme switcher
* [ ] Built-in quiz interactivity
* [ ] Import/export course metadata
* [ ] Mobile app wrapper
* [ ] Self hosted Docker Deployment

---

## 💬 Community

Join the development, suggest features, or ask questions via:

* GitHub Issues: [https://github.com/WhiskeyCoder/OfflineU/issues](https://github.com/WhiskeyCoder/OfflineU/issues)

---

## 🛡️ License

MIT License — Use freely, modify locally, share widely.

---

## ✨ Authors & Contributors

Built with ❤️ by [@WhiskeyCoder](https://github.com/WhiskeyCoder)

**Contributors:**
- [@rakanbakir](https://github.com/rakanbakir) - UI/UX improvements, smart folder finder, file dialog integration

Inspired by the dream of **learning freely, offline, and without limits.**
