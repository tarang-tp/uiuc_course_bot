import re
import datetime
import uuid
import io

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
    # Regex to capture: Course ID, Days, Time
    pattern = r"([A-Za-z]+\s*\d+)\s+([A-Za-z]+)\s+(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)"
    
    # Standard UIUC Fall 2026 instruction dates
    start_date_map = {
        'MO': '20260824',
        'TU': '20260825',
        'WE': '20260826',
        'TH': '20260827',
        'FR': '20260828',
        'SA': '20260829',
        'SU': '20260830'
    }
    
    # Semester ends on Wednesday, Dec 9, 2026
    until_date = "20261209T235959"
    
    # Split by comma
    chunks = schedule_string.split(',')
    parsed_courses = []
    
    ics_events = []
    dtstamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
            
        match = re.search(pattern, chunk)
        if not match:
            print(f"Warning: could not parse chunk '{chunk}'")
            continue
            
        raw_course = match.group(1)
        raw_days = match.group(2)
        raw_time = match.group(3)
        
        # Standardize course ID (e.g. cs225 -> CS 225)
        course_match = re.match(r"([A-Za-z]+)\s*(\d+)", raw_course)
        if course_match:
            course_id = f"{course_match.group(1).upper()} {course_match.group(2)}"
        else:
            course_id = raw_course.upper()
            
        days = parse_days(raw_days)
        if not days:
            print(f"Warning: could not parse days for chunk '{chunk}'")
            continue
            
        hour, minute = parse_time(raw_time)
        
        # Map to earliest day to define DTSTART
        day_order = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
        sorted_days = sorted(days, key=lambda d: day_order.index(d))
        earliest_day = sorted_days[0]
        start_date_str = start_date_map[earliest_day]
        
        # Duration: 80 mins for TU/TH, 50 mins otherwise
        is_tuth = 'TU' in days and 'TH' in days and len(days) == 2
        duration_mins = 80 if is_tuth else 50
        
        # Calculate start and end datetimes
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
        
    # Construct complete VCALENDAR content
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//UIUC Course Bot//Schedule Exporter//EN
{chr(10).join(ics_events)}
END:VCALENDAR"""
    
    # Standardize newlines to CRLF as per iCalendar spec
    ics_content = ics_content.replace("\r\n", "\n").replace("\n", "\r\n")
    
    # Save into in-memory BytesIO
    buf = io.BytesIO()
    buf.write(ics_content.encode('utf-8'))
    buf.seek(0)
    
    return buf, parsed_courses

if __name__ == "__main__":
    test_input = "cs225 mwf 11:00, math241 tth 13:00"
    print(f"Testing input: '{test_input}'")
    buf, courses = generate_ics(test_input)
    if buf:
        print("\nSuccessfully generated ICS calendar!")
        print(f"Parsed courses count: {len(courses)}")
        for c in courses:
            print(f"- {c['course_id']}: days={c['days']}, time={c['time']} ({c['duration']} mins)")
        
        print("\nFirst 10 lines of generated ICS file content:")
        content = buf.read().decode('utf-8')
        lines = content.split("\r\n")
        for line in lines[:15]:
            print(line)
            
        with open("uiuc_schedule.ics", "wb") as f:
            f.write(content.encode('utf-8'))
        print("\nSaved output file to uiuc_schedule.ics for local inspection.")
    else:
        print("\nFailed to generate ICS file.")
