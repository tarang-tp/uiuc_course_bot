# UIUC Academic Discord Bot 🎓

A modern, highly-polished Discord bot designed for University of Illinois Urbana-Champaign (UIUC) students. It aggregates historical course GPA data, catalog attributes, outstanding teacher rankings, and exports class schedules to iCalendar (.ics) format.

---

## 🌟 Features

### 1. `/course [course_code]`
Fetches details for any UIUC course (supports spaced/non-spaced inputs like `CS225` or `CS 225`).
- **Standard Catalog Metadata**: Title, description, attributes (Gen-Eds), and credit hours.
- **Recent Overall GPA (Post-2021)**: Reflects recent historical grading trends.
- **High-Resolution Visualizations**: Generates crisp 300 DPI transparent vertical bar charts showing grade distributions.
- **Instructor Disparity Dropdowns**: Swap between instructors to inspect individual grade profiles in real-time.
- **CITL Accolades Integration**: Individual instructors who earned placements on the CITL "List of Teachers Ranked as Excellent" receive a prominent accolade badge (e.g., `🏆 Dunfield, Nathan M (Ranked as Excellent 18x)`).

### 2. `/gened [category1] [category2] [min_gpa]`
Finds the top 5 easiest courses (sorted by GPA descending) that satisfy one or two simultaneous Gen-Ed categories (e.g. Advanced Composition + Western Culture) with a combined average GPA >= `min_gpa`.

### 3. `/calendar [schedule_string]`
Parses a raw class schedule string (e.g. `cs225 mwf 11:00, math241 tth 13:00` or `1:00pm`) and exports a standard, compliant `.ics` calendar file for the UIUC Fall 2026 semester.
- **TU/TH Duration Handling**: Tuesday/Thursday classes default to 80-minute blocks, others default to 50-minute blocks.
- **Recurrence Bounds**: Automatically recurs weekly until the end of instruction (Wednesday, December 9, 2026).

### 4. `/update_db` (Admin Only)
Forces an instant reload and re-compilation of the SQLite database using Wade Fagen-Ulmschneider's latest GPA and catalog datasets.

---

## ⚙️ How It Works (Database Aggregator)

The compiler (`build_db.py`) runs dynamically on setup or monthly in the background, executing:
- **Global Year Filter**: Excludes all records prior to **2021** to preserve recent trends.
- **Connected Components Cross-Listing**: Automatically groups cross-listed courses (like `CS 450`, `MATH 450`, `ECE 491`, and `CSE 401`) based on `"same as"` strings in catalog descriptions, combining their true grade pools and GPA averages.
- **Accolade Resolution**: Resolves CITL instructor accolade semesters using a fast prefix-bucket name matching algorithm that safely handles middle names, suffixes, spaces, hyphens, and truncations.

---

## 🚀 Installation & Setup

### 1. Clone & Install Dependencies
Ensure you have Python 3.10+ installed:
```bash
git clone https://github.com/yourusername/uiuc-discord-bot.git
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
