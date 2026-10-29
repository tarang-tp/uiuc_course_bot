# UIUC Academic Discord Bot 🎓

A modern, highly-polished Discord bot designed for University of Illinois Urbana-Champaign (UIUC) students. It aggregates historical course GPA data, catalog attributes, outstanding teacher rankings, curriculum paths, and exports class schedules to iCalendar (.ics) format.

---

## 🌟 Features

### 1. `/course [course_code]`
Fetches details for any UIUC course (supports spaced/non-spaced inputs like `CS225` or `CS 225`).
- **Standard Catalog Metadata**: Title, description, attributes (Gen-Eds), and credit hours.
- **Recent Overall GPA (Post-2021)**: Reflects recent historical grading trends.
- **Most Recent Offering**: Displays the most recent academic term the course was offered (e.g., `Spring 2026`).
- **High-Resolution Visualizations**: Generates crisp 300 DPI transparent vertical bar charts showing grade distributions.
- **Instructor Disparity Dropdowns**: Swap between instructors to inspect individual grade profiles in real-time.
- **CITL Accolades Integration**: Individual instructors who earned placements on the CITL "List of Teachers Ranked as Excellent" receive a prominent accolade badge (e.g., `🏆 Dunfield, Nathan M (Ranked as Excellent 18x)`).

### 2. `/gened [category1] [category2] [min_gpa] [keyword]`
Finds the top 5 easiest courses (sorted by GPA descending) that satisfy one or two simultaneous Gen-Ed categories (e.g. Advanced Composition + Western Culture) with a combined average GPA >= `min_gpa`.
- **Keyword/Topic Filter**: Optional parameter to filter results by specific topics or keywords (e.g., "writing", "history", "asia") matching course codes, titles, or catalog descriptions.

### 3. `/track [name]`
Visualizes common graduation tracks and technical course sequences (with autocomplete support).
- Outputs a beautifully formatted Discord embed containing a sequence roadmap drawn using box-drawing characters (e.g., `├──`, `└──`, `──►`).
- Supported tracks include: `Computer Science (Core)`, `Statistics & Computer Science`, `Software Systems Specialization`, and `Machine Learning & Data Science`.

### 4. `/calendar [schedule_string]`
Parses a raw class schedule string (e.g. `cs225 mwf 11:00, math241 tth 13:00`) and exports a standard, compliant `.ics` calendar file for the UIUC Fall 2026 semester.
- **TU/TH Duration Handling**: Tuesday/Thursday classes default to 80-minute blocks, others default to 50-minute blocks.
- **Recurrence Bounds**: Automatically recurs weekly until the end of instruction (Wednesday, December 9, 2026).

### 5. `/compare [course1] [course2]`
Compares two courses side by side.
- **Per-Course Stats**: Title, average GPA, number of students graded, credit hours, Gen-Ed attributes, most recent offering, and top instructor (highest GPA with at least 30 graded students).
- **Verdict**: States which course has the higher average GPA and by how much.

### 6. `/update_db` (Admin Only)
Forces an instant reload and re-compilation of the SQLite database using Wade Fagen-Ulmschneider's latest GPA, catalog, and CITL accolades datasets.

---

## ⚙️ How It Works (Database Aggregator)

The compiler (`build_db.py`) runs dynamically on setup or monthly in the background, executing:
- **Global Year Filter**: Excludes all records prior to **2021** to preserve recent trends.
- **Connected Components Cross-Listing**: Automatically groups cross-listed courses (like `CS 450`, `MATH 450`, `ECE 491`, and `CSE 401`) based on `"same as"` strings in catalog descriptions, combining their true grade pools and GPA averages.
- **Accolade Resolution**: Resolves CITL instructor accolade semesters using a fast prefix-bucket name matching algorithm that safely handles middle names, suffixes, spaces, hyphens, and truncations.
- **Chronological Sorting**: Catalog and GPA dataset records are sorted chronologically descending to accurately resolve the most recent term the course was offered.

---

## 🚀 Installation & Setup

### 1. Clone & Install Dependencies
Ensure you have Python 3.10+ installed:
```bash
git clone https://github.com/tarang-tp/uiuc-discord-bot.git
cd uiuc-discord-bot
pip install -r requirements.txt
```

*Note: Required libraries include `discord.py`, `matplotlib`, `pandas`, `numpy`, and `python-dotenv`.*

### 2. Setup Environment Configuration
Copy the template environment file:
```bash
cp .env.example .env
```
Open `.env` and fill in your details:
- `DISCORD_TOKEN`: Your Discord Bot token from the [Discord Developer Portal](https://discord.com/developers/applications).
- `TEST_GUILD_ID`: (Optional) Your Discord Server ID to instantly sync slash commands for testing.

### 3. Compile the Database
Run the compiler script to download the datasets and build the SQLite database:
```bash
python build_db.py
```

### 4. Run the Bot
Start the client:
```bash
python bot.py
```

---

## 🧪 Testing

Run validation scripts to verify components work as expected:
- `test_chart.py`: Generates a mock GPA distribution chart.
- `test_calendar.py`: Tests schedule token parsing and calendar exports.
- `test_accolades.py`: Verifies name matching accuracy for historical faculty accolades.
- `test_compilation_aggregates.py`: Verifies that cross-listed courses aggregate correctly.
- `test_track.py`: Asserts structural formatting and length limits for graduation tracks.
- `test_recent_offered.py`: Checks the courses table for the `most_recent_offered` column.
- `test_gened_keyword.py`: Validates Gen-Ed category queries combined with keyword searches.
- `test_compare.py`: Tests course code parsing, `/compare` data lookups, embed output, and command error paths.
