import os
import sqlite3
import urllib.request
import pandas as pd
import numpy as np
import re

# Configuration
GPA_CSV_URL = "https://raw.githubusercontent.com/wadefagen/shared-data/master/uiuc-gpa-dataset/uiuc-gpa-dataset.csv"
GPA_FALLBACK_URL = "https://raw.githubusercontent.com/wadefagen/datasets/master/gpa/uiuc-gpa-dataset.csv"
GPA_FALLBACK_URL_2 = "https://waf.cs.illinois.edu/discovery/gpa.csv"
CATALOG_CSV_URL = "https://raw.githubusercontent.com/wadefagen/datasets/master/course-catalog/uiuc-course-catalog.csv"
CATALOG_FALLBACK_URL = "https://waf.cs.illinois.edu/discovery/course-catalog.csv"
TRE_CSV_URL = "https://raw.githubusercontent.com/wadefagen/shared-data/master/teachers-ranked-as-excellent/teachers-ranked-as-excellent.csv"
TRE_FALLBACK_URL = "https://raw.githubusercontent.com/wadefagen/datasets/master/teachers-ranked-as-excellent/uiuc-tre-dataset.csv"
DB_NAME = "uiuc_bot.db"

# GPA Scale mapping for UIUC
GPA_WEIGHTS = {
    'A+': 4.00, 'A': 4.00, 'A-': 3.67,
    'B+': 3.33, 'B': 3.00, 'B-': 2.67,
    'C+': 2.33, 'C': 2.00, 'C-': 1.67,
    'D+': 1.33, 'D': 1.00, 'D-': 0.67,
    'F': 0.00
}
GRADE_COLUMNS = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'W']

def clean_string(s):
    return re.sub(r'[^A-Z]', '', s.upper())

def get_last_name_components(lname):
    parts = re.split(r'[- ]', lname.strip().upper())
    cleaned = [clean_string(p) for p in parts if clean_string(p)]
    return cleaned

def download_file(url, local_path):
    print(f"Downloading {url} to {local_path}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response, open(local_path, 'wb') as out_file:
        out_file.write(response.read())
    print("Download complete.")

def build_database():
    gpa_csv = "uiuc-gpa-dataset.csv"
    catalog_csv = "uiuc-course-catalog.csv"
    tre_csv = "uiuc-tre-dataset.csv"

    # Step 1: Download Datasets
    try:
        download_file(GPA_CSV_URL, gpa_csv)
    except Exception as e:
        print(f"Failed to download GPA dataset from primary URL: {e}. Trying fallback 1...")
        try:
            download_file(GPA_FALLBACK_URL, gpa_csv)
        except Exception as e1:
            print(f"Failed to download GPA dataset from fallback 1: {e1}. Trying fallback 2...")
            try:
                download_file(GPA_FALLBACK_URL_2, gpa_csv)
            except Exception as e2:
                print(f"Failed to download from fallback 2: {e2}")
                raise

    try:
        download_file(CATALOG_CSV_URL, catalog_csv)
    except Exception as e:
        print(f"Failed to download course catalog from primary URL: {e}. Trying fallback...")
        try:
            download_file(CATALOG_FALLBACK_URL, catalog_csv)
        except Exception as e2:
            print(f"Failed to download from fallback URL: {e2}")
            raise

    try:
        download_file(TRE_CSV_URL, tre_csv)
    except Exception as e:
        print(f"Failed to download TRE dataset from primary URL: {e}. Trying fallback...")
        try:
            download_file(TRE_FALLBACK_URL, tre_csv)
        except Exception as e2:
            print(f"Failed to download TRE dataset from fallback URL: {e2}")
            raise

    # Step 2: Load Course Catalog and Find Cross-Listings
    print("Processing Course Catalog for cross-listings...")
    course_to_group = {}
    try:
        df_cat_temp = pd.read_csv(catalog_csv)
        df_cat_temp.columns = [c.strip() for c in df_cat_temp.columns]
        df_cat_temp['Subject'] = df_cat_temp['Subject'].astype(str).str.strip().str.upper()
        df_cat_temp['Number'] = pd.to_numeric(df_cat_temp['Number'], errors='coerce')
        df_cat_temp = df_cat_temp.dropna(subset=['Subject', 'Number'])
        df_cat_temp['Number'] = df_cat_temp['Number'].astype(int)
        df_cat_temp['Course_ID'] = df_cat_temp['Subject'] + " " + df_cat_temp['Number'].astype(str)

        same_as_pattern = re.compile(r'(?:same as)\s+([^.]+)', re.IGNORECASE)
        connections = {}
        for _, row in df_cat_temp.iterrows():
            course_id = row['Course_ID']
            desc = str(row['Description'])
            match = same_as_pattern.search(desc)
            if match:
                same_as_text = match.group(1)
                rubrics = re.findall(r'([A-Z]{2,4})\s*(\d{3})', same_as_text.upper())
                linked_courses = [f"{subj} {num}" for subj, num in rubrics]
                if linked_courses:
                    connections.setdefault(course_id, set()).update(linked_courses)
                    for lc in linked_courses:
                        connections.setdefault(lc, set()).add(course_id)

        visited = set()
        components = []
        for node in list(connections.keys()):
            if node not in visited:
                component = set()
                queue = [node]
                while queue:
                    curr = queue.pop(0)
                    if curr not in visited:
                        visited.add(curr)
                        component.add(curr)
                        for neighbor in connections.get(curr, []):
                            if neighbor not in visited:
                                queue.append(neighbor)
                if len(component) > 1:
                    components.append(component)

        for comp in components:
            comp_list = list(comp)
            for course in comp_list:
                course_to_group[course] = comp_list
        print(f"Mapped {len(course_to_group)} courses to cross-listed groups from catalog.")
    except Exception as e:
        print(f"Warning: Failed to parse catalog cross-listings: {e}")

    # Now load and process GPA data
    print("Processing GPA dataset...")
    df_gpa = pd.read_csv(gpa_csv)
    df_gpa.columns = [c.strip() for c in df_gpa.columns]

    # Global Year Filter (Year >= 2021)
    if 'Year' in df_gpa.columns:
        df_gpa['Year'] = pd.to_numeric(df_gpa['Year'], errors='coerce')
        df_gpa = df_gpa[df_gpa['Year'] >= 2021]
        print(f"Filtered raw GPA rows (Year >= 2021): {len(df_gpa)}")

    # Check for core columns
    required_gpa_cols = ['Subject', 'Number', 'Primary Instructor']
    for col in required_gpa_cols:
        if col not in df_gpa.columns:
            normalized_cols = {c.lower().replace('_', ' '): c for c in df_gpa.columns}
            normalized_target = col.lower().replace('_', ' ')
            if normalized_target in normalized_cols:
                df_gpa.rename(columns={normalized_cols[normalized_target]: col}, inplace=True)
            else:
                raise ValueError(f"Required column '{col}' missing from GPA dataset columns: {list(df_gpa.columns)}")

    # Ensure grades columns are numeric and handle missing values
    for col in GRADE_COLUMNS:
        if col in df_gpa.columns:
            df_gpa[col] = pd.to_numeric(df_gpa[col], errors='coerce').fillna(0).astype(int)
        else:
            df_gpa[col] = 0

    # Format Course_ID
    df_gpa['Subject'] = df_gpa['Subject'].astype(str).str.strip().str.upper()
    df_gpa['Number'] = pd.to_numeric(df_gpa['Number'], errors='coerce')
    df_gpa = df_gpa.dropna(subset=['Subject', 'Number'])
    df_gpa['Number'] = df_gpa['Number'].astype(int)
    df_gpa['Course_ID'] = df_gpa['Subject'] + " " + df_gpa['Number'].astype(str)

    # Clean Instructor name
    df_gpa['Primary Instructor'] = df_gpa['Primary Instructor'].astype(str).str.strip()
    df_gpa = df_gpa[df_gpa['Primary Instructor'] != '']
    df_gpa = df_gpa[~df_gpa['Primary Instructor'].str.lower().isin(['us', 'unknown', 'nan', 'none'])]

    # Map each Course_ID to its cross-listed group representative
    course_to_rep = {}
    for course, group in course_to_group.items():
        rep = sorted(group)[0]
        course_to_rep[course] = rep

    df_gpa['Group_Rep'] = df_gpa['Course_ID'].map(lambda x: course_to_rep.get(x, x))

    # Group GPA rows by Group_Rep and Primary Instructor
    print("Grouping GPA data...")
    gpa_grouped = df_gpa.groupby(['Group_Rep', 'Primary Instructor'])[GRADE_COLUMNS].sum().reset_index()

    # Aggregate overall stats for each course under "ALL INSTRUCTORS COMBINED"
    print("Aggregating overall course stats...")
    gpa_combined = df_gpa.groupby(['Group_Rep'])[GRADE_COLUMNS].sum().reset_index()
    gpa_combined['Primary Instructor'] = 'ALL INSTRUCTORS COMBINED'

    # Combine both datasets
    gpa_grouped = pd.concat([gpa_grouped, gpa_combined], ignore_index=True)

    # Expand Group_Rep back to all original Course_IDs in the group
    print("Expanding cross-listed course rows...")
    expanded_rows = []
    for _, row in gpa_grouped.iterrows():
        rep = row['Group_Rep']
        if rep in course_to_group:
            members = course_to_group[rep]
            for member in members:
                new_row = row.copy()
                new_row['Course_ID'] = member
                expanded_rows.append(new_row)
        else:
            new_row = row.copy()
            new_row['Course_ID'] = rep
            expanded_rows.append(new_row)

    gpa_grouped = pd.DataFrame(expanded_rows)
    if 'Group_Rep' in gpa_grouped.columns:
        gpa_grouped = gpa_grouped.drop(columns=['Group_Rep'])

    # Calculate weighted average GPA
    gpa_gpts = []
    total_graded_students = []
    total_students_list = []

    for _, row in gpa_grouped.iterrows():
        total_pts = 0.0
        graded_count = 0
        total_count = 0

        for grade in GRADE_COLUMNS:
            count = int(row[grade])
            total_count += count
            if grade in GPA_WEIGHTS:
                total_pts += count * GPA_WEIGHTS[grade]
                graded_count += count

        avg_gpa = total_pts / graded_count if graded_count > 0 else 0.0
        gpa_gpts.append(round(avg_gpa, 4))
        total_graded_students.append(graded_count)
        total_students_list.append(total_count)

    gpa_grouped['Average_GPA'] = gpa_gpts
    gpa_grouped['Total_Graded'] = total_graded_students
    gpa_grouped['Total_Students'] = total_students_list

    # Step 3: Load and Process Course Catalog
    print("Processing Course Catalog...")
    df_cat = pd.read_csv(catalog_csv)
    df_cat.columns = [c.strip() for c in df_cat.columns]

    # Normalize columns
    df_cat['Subject'] = df_cat['Subject'].astype(str).str.strip().str.upper()
    df_cat['Number'] = pd.to_numeric(df_cat['Number'], errors='coerce')
    df_cat = df_cat.dropna(subset=['Subject', 'Number'])
    df_cat['Number'] = df_cat['Number'].astype(int)
    df_cat['Course_ID'] = df_cat['Subject'] + " " + df_cat['Number'].astype(str)

    # Dedup catalog, keeping the latest offering (based on YearTerm or Year if exists, or just first)
    if 'YearTerm' in df_cat.columns:
        df_cat = df_cat.sort_values(by='YearTerm', ascending=False)
    elif 'Year' in df_cat.columns:
        df_cat = df_cat.sort_values(by='Year', ascending=False)

    df_cat_dedup = df_cat.drop_duplicates(subset=['Course_ID'], keep='first').copy()

    # Select catalog columns
    catalog_cols_map = {
        'Course_ID': 'course_id',
        'Subject': 'subject',
        'Number': 'number',
        'Name': 'title',
        'Description': 'description',
        'Credit Hours': 'credit_hours',
        'Degree Attributes': 'degree_attributes'
    }

    # In case catalog does not have Name, try Course Title
    if 'Name' not in df_cat_dedup.columns and 'Course Title' in df_cat_dedup.columns:
        df_cat_dedup.rename(columns={'Course Title': 'Name'}, inplace=True)

    for col in catalog_cols_map.keys():
        if col not in df_cat_dedup.columns:
            df_cat_dedup[col] = "N/A"

    df_cat_final = df_cat_dedup[list(catalog_cols_map.keys())].rename(columns=catalog_cols_map)

    # Step 4: Handle courses in GPA dataset but missing in Course Catalog
    # This prevents the bot from displaying blank info when a course is historical
    gpa_courses = set(gpa_grouped['Course_ID'].unique())
    catalog_courses = set(df_cat_final['course_id'].unique())
    missing_courses = gpa_courses - catalog_courses

    if missing_courses:
        print(f"Found {len(missing_courses)} courses in GPA dataset that are missing in the catalog. Adding stubs...")
        # Get course title from original GPA dataset for these missing courses
        # We find the first occurrence of Course Title for each course ID in df_gpa
        gpa_titles = df_gpa.drop_duplicates(subset=['Course_ID'], keep='first')[['Course_ID', 'Subject', 'Number', 'Course Title']]
        
        stubs = []
        for course_id in missing_courses:
            row_data = gpa_titles[gpa_titles['Course_ID'] == course_id]
            if not row_data.empty:
                subj = row_data.iloc[0]['Subject']
                num = int(row_data.iloc[0]['Number'])
                title = row_data.iloc[0]['Course Title']
            else:
                parts = course_id.split()
                subj = parts[0]
                num = int(parts[1]) if len(parts) > 1 else 0
                title = f"{course_id} (Historical Course)"

            stubs.append({
                'course_id': course_id,
                'subject': subj,
                'number': num,
                'title': title,
                'description': "No description available in the current course catalog. This may be a historical course.",
                'credit_hours': "N/A",
                'degree_attributes': "N/A"
            })
        
        df_stubs = pd.DataFrame(stubs)
        df_cat_final = pd.concat([df_cat_final, df_stubs], ignore_index=True)

    # Step 5: Save to SQLite Database
    print(f"Saving compiled data to SQLite database '{DB_NAME}'...")
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create Tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        course_id TEXT PRIMARY KEY,
        subject TEXT NOT NULL,
        number INTEGER NOT NULL,
        title TEXT,
        description TEXT,
        credit_hours TEXT,
        degree_attributes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpa_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id TEXT NOT NULL,
        instructor TEXT NOT NULL,
        ap INTEGER DEFAULT 0,
        a INTEGER DEFAULT 0,
        am INTEGER DEFAULT 0,
        bp INTEGER DEFAULT 0,
        b INTEGER DEFAULT 0,
        bm INTEGER DEFAULT 0,
        cp INTEGER DEFAULT 0,
        c INTEGER DEFAULT 0,
        cm INTEGER DEFAULT 0,
        dp INTEGER DEFAULT 0,
        d INTEGER DEFAULT 0,
        dm INTEGER DEFAULT 0,
        f INTEGER DEFAULT 0,
        w INTEGER DEFAULT 0,
        average_gpa REAL DEFAULT 0.0,
        total_graded INTEGER DEFAULT 0,
        total_students INTEGER DEFAULT 0,
        FOREIGN KEY (course_id) REFERENCES courses (course_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS instructor_accolades (
        instructor TEXT PRIMARY KEY,
        excellent_count INTEGER NOT NULL
    )
    """)

    # Populate Courses
    df_cat_final.to_sql('courses', conn, if_exists='append', index=False)

    # Prepare GPA for insertion
    gpa_stats_db = gpa_grouped.rename(columns={
        'Course_ID': 'course_id',
        'Primary Instructor': 'instructor',
        'A+': 'ap',
        'A': 'a',
        'A-': 'am',
        'B+': 'bp',
        'B': 'b',
        'B-': 'bm',
        'C+': 'cp',
        'C': 'c',
        'C-': 'cm',
        'D+': 'dp',
        'D': 'd',
        'D-': 'dm',
        'F': 'f',
        'W': 'w',
        'Average_GPA': 'average_gpa',
        'Total_Graded': 'total_graded',
        'Total_Students': 'total_students'
    })

    # Save to SQLite
    gpa_stats_db.to_sql('gpa_stats', conn, if_exists='append', index=False)

    # Process and Match CITL Teachers Ranked as Excellent dataset
    print("Processing CITL Teachers Ranked as Excellent accolades...")
    try:
        df_tre = pd.read_csv(tre_csv)
        df_tre['lname'] = df_tre['lname'].astype(str).str.strip().str.upper()
        df_tre['fname'] = df_tre['fname'].astype(str).str.strip().str.upper()
        df_tre = df_tre.dropna(subset=['lname', 'fname', 'term'])
        
        df_tre['first_initial'] = df_tre['fname'].str[0]
        # Drop duplicate terms to count unique semesters
        df_tre_unique = df_tre.drop_duplicates(subset=['lname', 'first_initial', 'term'])
        
        # Build optimized lookup maps: tre_dict: lname -> {first_initial -> set(terms)}
        tre_dict = {}
        tre_prefix_buckets = {}
        for _, row in df_tre_unique.iterrows():
            lname = row['lname']
            first_init = row['first_initial']
            term = row['term']
            if lname and first_init and term:
                tre_dict.setdefault(lname, {}).setdefault(first_init, set()).add(term)
                prefix = lname[:4]
                tre_prefix_buckets.setdefault(prefix, set()).add(lname)
                
        # Get unique database instructors
        db_instructors = gpa_stats_db['instructor'].unique()
        accolades_records = []
        for inst in db_instructors:
            if not inst or inst == 'ALL INSTRUCTORS COMBINED' or ',' not in inst:
                continue
                
            parts = inst.split(',', 1)
            db_lname = parts[0].strip()
            db_fname = parts[1].strip()
            db_lname_comp = get_last_name_components(db_lname)
            db_first_init = db_fname[0].upper() if db_fname else ''
            
            if not db_lname_comp or not db_first_init:
                continue
                
            candidates = set()
            for comp in db_lname_comp:
                if comp in tre_dict:
                    candidates.add(comp)
                if len(comp) >= 5:
                    prefix = comp[:4]
                    for key in tre_prefix_buckets.get(prefix, []):
                        if len(key) >= 5:
                            if key.startswith(comp) or comp.startswith(key):
                                candidates.add(key)
                                
            matched_terms = set()
            for key in candidates:
                if key in tre_dict and db_first_init in tre_dict[key]:
                    matched_terms.update(tre_dict[key][db_first_init])
                        
            if matched_terms:
                accolades_records.append((inst, len(matched_terms)))
                
        if accolades_records:
            cursor.executemany(
                "INSERT INTO instructor_accolades (instructor, excellent_count) VALUES (?, ?)",
                accolades_records
            )
            print(f"Successfully loaded {len(accolades_records)} instructor accolade records into database.")
    except Exception as e:
        print(f"Error processing CITL teacher accolades: {e}")

    # Index for fast search
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpa_stats_course ON gpa_stats(course_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_subj_num ON courses(subject, number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_instructor_accolades_inst ON instructor_accolades(instructor)")

    conn.commit()
    conn.close()
    print("Database built successfully!")

    # Cleanup temporary CSVs
    if os.path.exists(gpa_csv):
        os.remove(gpa_csv)
    if os.path.exists(catalog_csv):
        os.remove(catalog_csv)
    if os.path.exists(tre_csv):
        os.remove(tre_csv)
    print("Temporary files cleaned up.")

if __name__ == "__main__":
    build_database()
