import os
import sqlite3
import html
import re
import datetime
import uuid
import io
# pyrefly: ignore [missing-import]
import discord
# pyrefly: ignore [missing-import]
from discord import app_commands
# pyrefly: ignore [missing-import]
from discord.ext import commands, tasks
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Import our chart generator
import chart_gen

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DB_NAME = "uiuc_bot.db"

# Setup Bot with Intents
intents = discord.Intents.default()
intents.message_content = True

class UIUCBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.auto_update_db.start()

    @tasks.loop(hours=720)  # Auto-update database monthly
    async def auto_update_db(self):
        import asyncio
        import build_db
        print("Starting monthly background database auto-update...")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, build_db.build_database)
            print("Monthly background database auto-update completed successfully.")
        except Exception as e:
            print(f"Failed to auto-update database in background: {e}")

    @auto_update_db.before_loop
    async def before_auto_update_db(self):
        await self.wait_until_ready()

bot = UIUCBot()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def extract_gened_codes(attributes):
    """Extract standard Gen-Ed codes from catalog attribute strings."""
    if not attributes or attributes == "N/A":
        return []
    codes = []
    attr_lower = attributes.lower()
    if 'advanced composition' in attr_lower:
        codes.append('ACP')
    if 'cultural studies - western' in attr_lower:
        codes.append('WCC')
    if 'cultural studies - non-west' in attr_lower:
        codes.append('NW')
    if 'cultural studies - us minority' in attr_lower:
        codes.append('US')
    if 'humanities' in attr_lower:
        codes.append('HUM')
    if 'social & beh sci' in attr_lower:
        codes.append('SBS')
    if 'nat sci & tech' in attr_lower:
        codes.append('NAT')
    return codes

# Interactive View and Select components for Professor Selection
class ProfessorSelect(discord.ui.Select):
    def __init__(self, course_id, options):
        super().__init__(
            placeholder="Choose a professor to view GPA disparities...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"select_prof:{course_id}"
        )
        self.course_id = course_id

    async def callback(self, interaction: discord.Interaction):
        instructor = self.values[0]
        
        # Defer message update so matplotlib can work in background
        await interaction.response.defer()
        
        # Query the grade counts for this instructor and course
        conn = get_db_connection()
        row = conn.execute(
            """
            SELECT ap, a, am, bp, b, bm, cp, c, cm, dp, d, dm, f, w, average_gpa, total_graded
            FROM gpa_stats 
            WHERE course_id = ? AND instructor = ?
            """,
            (self.course_id, instructor)
        ).fetchone()
        
        course_info = conn.execute(
            "SELECT title, description, credit_hours, degree_attributes FROM courses WHERE course_id = ?",
            (self.course_id,)
        ).fetchone()

        # Query outstanding teacher accolades
        excellent_count = 0
        if instructor != 'ALL INSTRUCTORS COMBINED':
            try:
                accolade_row = conn.execute(
                    "SELECT excellent_count FROM instructor_accolades WHERE instructor = ?",
                    (instructor,)
                ).fetchone()
                if accolade_row:
                    excellent_count = accolade_row['excellent_count']
            except sqlite3.OperationalError:
                pass

        conn.close()

        if not row:
            await interaction.followup.send("Error: Grade data not found for selection.", ephemeral=True)
            return

        # Map row counts to list in correct order for chart_gen
        grade_counts = [
            row['ap'], row['a'], row['am'],
            row['bp'], row['b'], row['bm'],
            row['cp'], row['c'], row['cm'],
            row['dp'], row['d'], row['dm'],
            row['f'], row['w']
        ]

        # Generate the chart
        try:
            chart_stream = chart_gen.generate_gpa_chart(grade_counts)
        except Exception as e:
            await interaction.followup.send(f"Error generating GPA chart: {e}", ephemeral=True)
            return

        # Prepare File and Embed update
        file = discord.File(chart_stream, filename="gpa_chart.png")
        
        embed = interaction.message.embeds[0].copy()
        embed.set_image(url="attachment://gpa_chart.png")
        
        embed.clear_fields()
        
        # Prepare Course Explorer link
        subj, num = self.course_id.split(maxsplit=1)
        course_explorer_url = f"https://courses.illinois.edu/schedule/DEFAULT/DEFAULT/{subj}/{num}"
        course_title_escaped = html.unescape(course_info['title'])
        course_explorer_link = f"[{self.course_id}: {course_title_escaped}]({course_explorer_url})"

        if instructor == 'ALL INSTRUCTORS COMBINED':
            embed.title = f"{self.course_id}: {course_title_escaped}"
            
            # Reconstruct default overall view fields
            degree_attributes = course_info['degree_attributes']
            attributes_val = degree_attributes if degree_attributes != "N/A" else "None"
                
            embed.add_field(name="Attributes", value=attributes_val, inline=False)
            embed.add_field(name="Credit Hours", value=course_info['credit_hours'] or "N/A", inline=False)
            embed.add_field(name="Average Recent GPA", value=f"{row['average_gpa']:.2f}", inline=False)
            embed.add_field(name="Course Explorer", value=course_explorer_link, inline=False)
        else:
            if excellent_count > 0:
                embed.title = f"{self.course_id} GPA Disparity - 🏆 {instructor} (Ranked as Excellent {excellent_count}x)"
            else:
                embed.title = f"{self.course_id} GPA Disparity - {instructor}"
            
            # Instructor specific fields
            credit_hours = course_info['credit_hours'] if course_info else "N/A"
            embed.add_field(name="Credit Hours", value=credit_hours, inline=False)
            embed.add_field(name="Instructor Weighted GPA", value=f"{row['average_gpa']:.2f}", inline=False)
            embed.add_field(name="Total Graded Students", value=f"{row['total_graded']:,}", inline=False)
            embed.add_field(name="Course Explorer", value=course_explorer_link, inline=False)

        # Update default selected option in dropdown
        for option in self.options:
            if option.value == instructor:
                option.default = True
            else:
                option.default = False

        # Edit original message with new file, embed and updated view
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self.view)

class CourseView(discord.ui.View):
    def __init__(self, course_id, options):
        super().__init__(timeout=180.0)
        self.add_item(ProfessorSelect(course_id, options))

# Slash command `/course [course]`
@bot.tree.command(name="course", description="Get course details and overall or instructor GPA analysis")
@app_commands.describe(
    course="The course code (e.g., CS225, MATH 241, ace240)"
)
async def course_command(interaction: discord.Interaction, course: str):
    # Parse and normalize course input (handles formatting with/without spaces)
    match = re.match(r"^\s*([A-Za-z]+)\s*(\d+)\s*$", course)
    if not match:
        await interaction.response.send_message(
            f"❌ Invalid course format. Please search using a format like `CS225` or `CS 225`.",
            ephemeral=True
        )
        return
        
    subj_norm = match.group(1).upper()
    number = int(match.group(2))
    course_id = f"{subj_norm} {number}"

    # Defer response since chart generation is synchronous and takes time
    await interaction.response.defer()

    conn = get_db_connection()
    # 1. Fetch Course Info
    course_info = conn.execute(
        "SELECT title, description, credit_hours, degree_attributes FROM courses WHERE course_id = ?",
        (course_id,)
    ).fetchone()

    if not course_info:
        conn.close()
        await interaction.followup.send(
            f"❌ Course `{course_id}` was not found in the UIUC Catalog or GPA Database."
        )
        return

    # 2. Fetch overall GPA stats for this course
    overall_stats = conn.execute(
        """
        SELECT ap, a, am, bp, b, bm, cp, c, cm, dp, d, dm, f, w, average_gpa, total_graded
        FROM gpa_stats 
        WHERE course_id = ? AND instructor = 'ALL INSTRUCTORS COMBINED'
        """,
        (course_id,)
    ).fetchone()

    # 3. Fetch up to top 24 instructors (excluding the combined row) sorted by volume of graded students
    instructors = conn.execute(
        """
        SELECT instructor, average_gpa, total_graded 
        FROM gpa_stats 
        WHERE course_id = ? AND instructor != 'ALL INSTRUCTORS COMBINED'
        ORDER BY total_graded DESC 
        LIMIT 24
        """,
        (course_id,)
    ).fetchall()
    conn.close()

    # Build Course Details Embed
    desc = html.unescape(course_info['description']) if course_info['description'] else "No description available."
    if len(desc) > 1000:
        desc = desc[:997] + "..."
        
    embed = discord.Embed(
        title=f"{course_id}: {html.unescape(course_info['title'])}",
        description=desc,
        color=discord.Color.blue()
    )
    
    # Format Attributes (Gen-Ed markers)
    degree_attributes = course_info['degree_attributes']
    attributes_val = degree_attributes if degree_attributes != "N/A" else "None"

    embed.add_field(name="Attributes", value=attributes_val, inline=False)
    embed.add_field(name="Credit Hours", value=course_info['credit_hours'] or "N/A", inline=False)
    
    if overall_stats:
        embed.add_field(name="Average Recent GPA", value=f"{overall_stats['average_gpa']:.2f}", inline=False)
    else:
        embed.add_field(name="Average Recent GPA", value="N/A", inline=False)

    # Add Course Explorer link
    subj, num = course_id.split(maxsplit=1)
    course_explorer_url = f"https://courses.illinois.edu/schedule/DEFAULT/DEFAULT/{subj}/{num}"
    course_title_escaped = html.unescape(course_info['title'])
    course_explorer_link = f"[{course_id}: {course_title_escaped}]({course_explorer_url})"
    embed.add_field(name="Course Explorer", value=course_explorer_link, inline=False)

    # If overall GPA statistics exist, build and attach the overall distribution chart
    file = None
    if overall_stats:
        grade_counts = [
            overall_stats['ap'], overall_stats['a'], overall_stats['am'],
            overall_stats['bp'], overall_stats['b'], overall_stats['bm'],
            overall_stats['cp'], overall_stats['c'], overall_stats['cm'],
            overall_stats['dp'], overall_stats['d'], overall_stats['dm'],
            overall_stats['f'], overall_stats['w']
        ]
        try:
            chart_stream = chart_gen.generate_gpa_chart(grade_counts)
            file = discord.File(chart_stream, filename="gpa_chart.png")
            embed.set_image(url="attachment://gpa_chart.png")
        except Exception as e:
            print(f"Error generating overall chart: {e}")

    # Build Select Options
    options = []
    
    # If overall data is present, prepend it as the default/first option
    if overall_stats:
        options.append(
            discord.SelectOption(
                label="Overall (All Instructors Combined)",
                value="ALL INSTRUCTORS COMBINED",
                description=f"Combined grade metrics across all instructors (Avg GPA: {overall_stats['average_gpa']:.2f})",
                default=True
            )
        )

    # Add individual instructors
    for inst in instructors:
        name = inst['instructor']
        avg_gpa = inst['average_gpa']
        total_st = inst['total_graded']
        
        options.append(
            discord.SelectOption(
                label=name[:100],
                value=name[:100],
                description=f"Avg GPA: {avg_gpa:.2f} ({total_st:,} students)"[:100]
            )
        )

    # Attach the custom dropdown view if we have select options (at least one)
    if options:
        view = CourseView(course_id, options)
        if file:
            await interaction.followup.send(embed=embed, file=file, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)
    else:
        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

# New slash command `/gened [category1] [category2] [min_gpa]`
@bot.tree.command(name="gened", description="Find the easiest Gen-Ed courses matching one or two constraints")
@app_commands.describe(
    category1="The first Gen-Ed category to filter for",
    category2="An optional second Gen-Ed category to filter for (simultaneous requirement)",
    min_gpa="The minimum historical average GPA required (default: 3.4)"
)
@app_commands.choices(category1=[
    app_commands.Choice(name="Advanced Composition (ACP)", value="ACP"),
    app_commands.Choice(name="Western Comparative Culture (WCC)", value="WCC"),
    app_commands.Choice(name="Non-Western Culture (NW)", value="NW"),
    app_commands.Choice(name="US Minority Culture (US)", value="US"),
    app_commands.Choice(name="Humanities & the Arts (HUM)", value="HUM"),
    app_commands.Choice(name="Social & Behavioral Sciences (SBS)", value="SBS"),
    app_commands.Choice(name="Natural Sciences & Technology (NAT)", value="NAT")
])
@app_commands.choices(category2=[
    app_commands.Choice(name="Advanced Composition (ACP)", value="ACP"),
    app_commands.Choice(name="Western Comparative Culture (WCC)", value="WCC"),
    app_commands.Choice(name="Non-Western Culture (NW)", value="NW"),
    app_commands.Choice(name="US Minority Culture (US)", value="US"),
    app_commands.Choice(name="Humanities & the Arts (HUM)", value="HUM"),
    app_commands.Choice(name="Social & Behavioral Sciences (SBS)", value="SBS"),
    app_commands.Choice(name="Natural Sciences & Technology (NAT)", value="NAT")
])
async def gened_command(
    interaction: discord.Interaction, 
    category1: app_commands.Choice[str], 
    category2: app_commands.Choice[str] = None, 
    min_gpa: float = 3.4
):
    # Defer response to ensure smooth SQL join execution
    await interaction.response.defer()

    category_map = {
        'ACP': '%advanced composition%',
        'WCC': '%cultural studies - western%',
        'NW': '%cultural studies - non-west%',
        'US': '%cultural studies - us minority%',
        'HUM': '%humanities%',
        'SBS': '%social & beh sci%',
        'NAT': '%nat sci & tech%'
    }
    
    category_names = {
        'ACP': 'Advanced Composition (ACP)',
        'WCC': 'Western Comparative Culture (WCC)',
        'NW': 'Non-Western Culture (NW)',
        'US': 'US Minority Culture (US)',
        'HUM': 'Humanities & the Arts (HUM)',
        'SBS': 'Social & Behavioral Sciences (SBS)',
        'NAT': 'Natural Sciences & Technology (NAT)'
    }

    cat1_val = category1.value
    cat1_name = category_names[cat1_val]
    cat1_pattern = category_map[cat1_val]
    
    conn = get_db_connection()
    if category2:
        cat2_val = category2.value
        cat2_name = category_names[cat2_val]
        cat2_pattern = category_map[cat2_val]
        search_title = f"{cat1_name} & {cat2_name}"
        
        query = """
            SELECT c.course_id, c.title, g.average_gpa, c.credit_hours
            FROM courses c
            JOIN gpa_stats g ON c.course_id = g.course_id
            WHERE g.instructor = 'ALL INSTRUCTORS COMBINED'
              AND g.average_gpa >= ?
              AND c.degree_attributes LIKE ?
              AND c.degree_attributes LIKE ?
            ORDER BY g.average_gpa DESC
            LIMIT 5
        """
        rows = conn.execute(query, (min_gpa, cat1_pattern, cat2_pattern)).fetchall()
    else:
        search_title = cat1_name
        query = """
            SELECT c.course_id, c.title, g.average_gpa, c.credit_hours
            FROM courses c
            JOIN gpa_stats g ON c.course_id = g.course_id
            WHERE g.instructor = 'ALL INSTRUCTORS COMBINED'
              AND g.average_gpa >= ?
              AND c.degree_attributes LIKE ?
            ORDER BY g.average_gpa DESC
            LIMIT 5
        """
        rows = conn.execute(query, (min_gpa, cat1_pattern)).fetchall()
        
    conn.close()

    if not rows:
        await interaction.followup.send(
            f"❌ No courses found satisfying **{search_title}** with a combined average GPA >= **{min_gpa:.2f}**."
        )
        return

    # Format the output using blockquote syntax styling (>)
    response_lines = [
        f"🏆 **Top 5 Easiest {search_title} Gen-Ed Courses** (Min GPA: {min_gpa:.2f}):\n"
    ]
    for row in rows:
        course_id = row['course_id']
        title = html.unescape(row['title'])
        avg_gpa = row['average_gpa']
        credits = row['credit_hours']
        response_lines.append(f"> **{course_id}**: {title} (Avg GPA: **{avg_gpa:.2f}** | Credits: {credits})")

    await interaction.followup.send("\n".join(response_lines))

# Slash command `/update_db` to manually reload database
@bot.tree.command(name="update_db", description="Force update the GPA and Course Catalog database (Admins only)")
@app_commands.checks.has_permissions(administrator=True)
async def update_db_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    import asyncio
    import build_db
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, build_db.build_database)
        await interaction.followup.send("✅ Database successfully updated with the latest Wade Fagen-Ulmschneider datasets!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to update database: {e}", ephemeral=True)

# Add error handler for permissions check
@update_db_command.error
async def update_db_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ You do not have permission to run this command. Administrator required.", ephemeral=True)

def parse_days(days_str):
    days_str = days_str.lower()
    days_map = []
    i = 0
    while i < len(days_str):
        char = days_str[i]
        if char == 'm':
            days_map.append('MO')
            i += 1
        elif char == 't':
            if i + 1 < len(days_str) and days_str[i+1] == 'h':
                days_map.append('TH')
                i += 2
            elif i + 1 < len(days_str) and days_str[i+1] == 'u':
                days_map.append('TU')
                i += 2
                if i + 1 < len(days_str) and days_str[i:i+2] == 'th':
                    days_map.append('TH')
                    i += 2
            elif i + 1 < len(days_str) and days_str[i+1] == 'r':
                days_map.append('TU')
                days_map.append('TH')
                i += 2
            else:
                days_map.append('TU')
                i += 1
        elif char == 'w':
            days_map.append('WE')
            i += 1
        elif char == 'h':
            days_map.append('TH')
            i += 1
        elif char == 'f':
            days_map.append('FR')
            i += 1
        elif char == 's':
            if i + 1 < len(days_str) and days_str[i+1] == 'u':
                days_map.append('SU')
                i += 2
            else:
                days_map.append('SA')
                i += 1
        else:
            i += 1
    seen = set()
    return [d for d in days_map if not (d in seen or seen.add(d))]

def parse_time(time_str):
    time_str = time_str.strip().lower()
    is_pm = 'pm' in time_str
    is_am = 'am' in time_str
    time_digits = time_str.replace('am', '').replace('pm', '').strip()
    if ':' in time_digits:
        parts = time_digits.split(':')
        hour = int(parts[0])
        minute = int(parts[1])
    else:
        if len(time_digits) >= 3:
            hour = int(time_digits[:-2])
            minute = int(time_digits[-2:])
        else:
            hour = int(time_digits)
            minute = 0
    if is_pm and hour < 12:
        hour += 12
    elif is_am and hour == 12:
        hour = 0
    return hour, minute

def generate_ics(schedule_string):
    pattern = r"([A-Za-z]+\s*\d+)\s+([A-Za-z]+)\s+(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)"
    start_date_map = {
        'MO': '20260824', 'TU': '20260825', 'WE': '20260826',
        'TH': '20260827', 'FR': '20260828', 'SA': '20260829', 'SU': '20260830'
    }
    until_date = "20261209T235959"
    chunks = schedule_string.split(',')
    parsed_courses = []
    ics_events = []
    dtstamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        match = re.search(pattern, chunk)
        if not match:
            continue
        raw_course = match.group(1)
        raw_days = match.group(2)
        raw_time = match.group(3)
        course_match = re.match(r"([A-Za-z]+)\s*(\d+)", raw_course)
        course_id = f"{course_match.group(1).upper()} {course_match.group(2)}" if course_match else raw_course.upper()
        days = parse_days(raw_days)
        if not days:
            continue
        hour, minute = parse_time(raw_time)
        day_order = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
        sorted_days = sorted(days, key=lambda d: day_order.index(d))
        earliest_day = sorted_days[0]
        start_date_str = start_date_map[earliest_day]
        is_tuth = 'TU' in days and 'TH' in days and len(days) == 2
        duration_mins = 80 if is_tuth else 50
        start_day_num = int(start_date_str[-2:])
        dt_start = datetime.datetime(2026, 8, start_day_num, hour, minute)
        dt_end = dt_start + datetime.timedelta(minutes=duration_mins)
        dtstart_str = dt_start.strftime("%Y%m%dT%H%M%S")
        dtend_str = dt_end.strftime("%Y%m%dT%H%M%S")
        uid = str(uuid.uuid4())
        byday_str = ",".join(days)
        event = f"""BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart_str}
DTEND:{dtend_str}
SUMMARY:{course_id}
RRULE:FREQ=WEEKLY;BYDAY={byday_str};UNTIL={until_date}
DESCRIPTION:UIUC Course Bot exported class schedule.
END:VEVENT"""
        ics_events.append(event)
        parsed_courses.append({
            'course_id': course_id,
            'days': days,
            'time': f"{hour:02d}:{minute:02d}",
            'duration': duration_mins
        })
    if not ics_events:
        return None, []
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//UIUC Course Bot//Schedule Exporter//EN
{chr(10).join(ics_events)}
END:VCALENDAR"""
    ics_content = ics_content.replace("\r\n", "\n").replace("\n", "\r\n")
    buf = io.BytesIO()
    buf.write(ics_content.encode('utf-8'))
    buf.seek(0)
    return buf, parsed_courses

# Slash command `/calendar [schedule_string]`
@bot.tree.command(name="calendar", description="Export a UIUC class schedule string to a standard .ics calendar file")
@app_commands.describe(
    schedule_string="Your schedule format (e.g. cs225 mwf 11:00, math241 tth 1:00pm)"
)
async def calendar_command(interaction: discord.Interaction, schedule_string: str):
    try:
        buf, parsed_courses = generate_ics(schedule_string)
        if not buf or not parsed_courses:
            await interaction.response.send_message(
                "❌ Could not parse any valid courses from your schedule input. Please verify the format.\n"
                "Example: `cs225 mwf 11:00, math241 tth 1:00pm`",
                ephemeral=True
            )
            return
        embed = discord.Embed(
            title="📅 UIUC Class Schedule Exported",
            description="Your class schedule has been successfully processed and converted to an iCalendar (.ics) file!\n\n"
                        "Download the attached file and click it to instantly import your entire Fall 2026 semester schedule into your calendar app (Google Calendar, Apple Calendar, Outlook, etc.).",
            color=discord.Color.green()
        )
        courses_value = ""
        for c in parsed_courses:
            days_fmt = ", ".join(c['days'])
            courses_value += f"• **{c['course_id']}**: {days_fmt} at {c['time']} ({c['duration']} mins)\n"
        embed.add_field(name="Processed Classes", value=courses_value, inline=False)
        embed.add_field(name="Semester Dates", value="• **Start**: Monday, Aug 24, 2026\n• **End**: Wednesday, Dec 9, 2026", inline=False)
        file = discord.File(buf, filename="uiuc_schedule.ics")
        await interaction.response.send_message(embed=embed, file=file)
    except Exception as e:
        await interaction.response.send_message(
            f"❌ An error occurred while generating your calendar: {e}",
            ephemeral=True
        )

TRACKS_DATA = {
    "Computer Science (Core)": {
        "description": "Foundational curriculum for the traditional Computer Science major, mapping core theory, systems, and mathematics sequences.",
        "roadmap": (
            "UIUC Computer Science Core Sequence:\n"
            "Year 1:\n"
            "├── MATH 221 (Calculus I)\n"
            "│    └── MATH 231 (Calculus II)\n"
            "│         └── MATH 257 (Linear Algebra) ──┐\n"
            "├── CS 124 (Intro to CS I)                 │\n"
            "│    └── CS 128 (Intro to CS II)           │\n"
            "│         ├── CS 173 (Discrete Math)       │\n"
            "│         └── CS 225 (Data Structures) ◄───┘\n"
            "│              ├── CS 233 (Computer Architecture)\n"
            "│              │    └── CS 341 (System Programming)\n"
            "│              └── CS 374 (Algorithms & Models)\n"
            "│                   └── CS 473 (Algorithms)"
        )
    },
    "Statistics & Computer Science": {
        "description": "Integrated curriculum tracking statistics, mathematical reasoning, and data structure progressions for the Stats & CS major.",
        "roadmap": (
            "UIUC Statistics & Computer Science Sequence:\n"
            "├── MATH 221 (Calculus I)\n"
            "│    └── MATH 231 (Calculus II)\n"
            "│         ├── MATH 257 (Linear Algebra) ──┐\n"
            "│         └── STAT 400 (Statistics I)      │\n"
            "│              └── STAT 410 (Statistics II)│\n"
            "│                   └── STAT 425 (Applied Regression)\n"
            "├── CS 124 (Intro to CS I)                 │\n"
            "│    └── CS 128 (Intro to CS II)           │\n"
            "│         ├── CS 173 (Discrete Math)       │\n"
            "│         └── CS 225 (Data Structures) ◄───┘\n"
            "│              └── CS 374 (Algorithms & Models)"
        )
    },
    "Software Systems Specialization": {
        "description": "Advanced technical sequence focusing on low-level systems architecture, networking, OS design, and distributed systems.",
        "roadmap": (
            "UIUC Systems Specialization Sequence:\n"
            "CS 225 (Data Structures)\n"
            " ├── CS 233 (Computer Architecture)\n"
            " │    └── CS 341 (System Programming)\n"
            " │         ├── CS 423 (Operating Systems)\n"
            " │         ├── CS 438 (Computer Networks)\n"
            " │         └── CS 425 (Distributed Systems)\n"
            " └── CS 433 (Advanced Computer Architecture)"
        )
    },
    "Machine Learning & Data Science": {
        "description": "Advanced specialized pathway tracking mathematical foundations, core probabilistic modeling, and machine learning architectures.",
        "roadmap": (
            "UIUC Machine Learning & Data Science Sequence:\n"
            "Prerequisites: CS 225, MATH 257, STAT 400\n"
            "├── MATH 257 (Linear Algebra) ────────────────────────┐\n"
            "├── STAT 400 (Mathematical Statistics I)              │\n"
            "│    └── STAT 410 (Mathematical Statistics II)        │\n"
            "│         └── STAT 425 (Applied Regression) ──────────┼─► CS 446 (Machine Learning)\n"
            "└── CS 225 (Data Structures)                          │    ├── CS 444 (Deep Learning)\n"
            "     ├── CS 361 (Probability & Stats for CS) ──► CS 446 │    └── CS 447 (Natural Language Proc)\n"
            "     └── CS 440 (Artificial Intelligence)             │\n"
            "          └── CS 443 (Reinforcement Learning) ◄───────┘"
        )
    }
}

# Slash command `/track [name]`
@bot.tree.command(name="track", description="Visualize common graduation tracks and technical course sequences")
@app_commands.describe(
    name="The UIUC curriculum track or specialization to visualize"
)
async def track_command(interaction: discord.Interaction, name: str):
    if name not in TRACKS_DATA:
        await interaction.response.send_message(
            f"❌ Track `{name}` is not defined. Please choose a valid track from the options.",
            ephemeral=True
        )
        return
        
    track_info = TRACKS_DATA[name]
    embed = discord.Embed(
        title=f"🎓 UIUC Curriculum Track - {name}",
        description=track_info["description"],
        color=discord.Color.dark_gold()
    )
    
    # Wrap roadmap sequence in a monospace python code block to display correctly
    roadmap_str = f"```\n{track_info['roadmap']}\n```"
    embed.add_field(name="Sequence Roadmap", value=roadmap_str, inline=False)
    
    await interaction.response.send_message(embed=embed)

@track_command.autocomplete('name')
async def track_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    choices = list(TRACKS_DATA.keys())
    return [
        app_commands.Choice(name=c, value=c)
        for c in choices if current.lower() in c.lower()
    ][:25]

@bot.event
async def on_ready():
    print(f"🤖 UIUC Bot is online as {bot.user}!")
    print("Syncing slash commands...")
    try:
        # If a specific test server guild ID is provided, sync to it immediately
        test_guild_id = os.getenv("TEST_GUILD_ID")
        if test_guild_id:
            guild = discord.Object(id=int(test_guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Sync complete: {len(synced)} commands registered to Guild ID {test_guild_id}")
        else:
            synced = await bot.tree.sync()
            print(f"✅ Sync complete: {len(synced)} commands registered globally")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN is missing. Please set it in a .env file.")
    else:
        bot.run(TOKEN)
