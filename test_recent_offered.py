import sqlite3
import os

def test_recent_offered():
    db_path = "uiuc_bot.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist. Run build_db.py first.")
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("Checking database for 'most_recent_offered' column...")
    
    # Check if column exists in the courses table schema
    cursor.execute("PRAGMA table_info(courses)")
    columns = [row['name'] for row in cursor.fetchall()]
    
    if 'most_recent_offered' not in columns:
        print("FAIL: 'most_recent_offered' column is NOT in courses table!")
        conn.close()
        return False
    
    print("PASS: 'most_recent_offered' column exists in courses table.")

    # Query a sample of courses to see their most recent offered term
    cursor.execute("""
        SELECT course_id, title, most_recent_offered 
        FROM courses 
        WHERE course_id IN ('CS 225', 'CS 124', 'MATH 241', 'MATH 220') 
        OR description LIKE '%Historical Course%'
        LIMIT 10
    """)
    rows = cursor.fetchall()
    
    print("\nSample Courses and their Most Recent Offering:")
    for row in rows:
        print(f" - {row['course_id']}: {row['title']} | Offered: {row['most_recent_offered']}")

    # Let's count how many have N/A vs real semesters
    cursor.execute("SELECT COUNT(*) as count FROM courses WHERE most_recent_offered != 'N/A' AND most_recent_offered IS NOT NULL")
    with_offered = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM courses")
    total_courses = cursor.fetchone()['count']

    print(f"\nStats: {with_offered} / {total_courses} courses have a valid 'most_recent_offered' value.")
    
    if with_offered == 0:
        print("FAIL: No courses have a valid 'most_recent_offered' value!")
        conn.close()
        return False

    print("PASS: Courses table has populated 'most_recent_offered' values.")
    conn.close()
    return True

if __name__ == "__main__":
    success = test_recent_offered()
    if success:
        print("\nAll recent offering verification checks PASSED successfully!")
    else:
        print("\nVerification checks FAILED.")
