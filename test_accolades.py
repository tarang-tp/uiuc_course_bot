import sqlite3
import os

def test_database_accolades():
    db_name = "uiuc_bot.db"
    if not os.path.exists(db_name):
        print(f"Error: {db_name} does not exist. Please run build_db.py first.")
        return False

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # 1. Check if the table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructor_accolades'")
    table_exists = cursor.fetchone()
    if not table_exists:
        print("FAIL: 'instructor_accolades' table does not exist in database!")
        conn.close()
        return False
    print("PASS: 'instructor_accolades' table exists.")

    # 2. Check if index exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_instructor_accolades_inst'")
    index_exists = cursor.fetchone()
    if not index_exists:
        print("FAIL: Index 'idx_instructor_accolades_inst' does not exist!")
        conn.close()
        return False
    print("PASS: Index 'idx_instructor_accolades_inst' exists.")

    # 3. Check some records
    test_cases = [
        ("Fagen-Ulmschnei, Wade A", 24),
        ("Fagen, Wade A", 24),
        ("Dunfield, Nathan M", 18),
        ("Tremacoldi Ross, Pedro", 1),
        ("Valdebenito Ram, Rocio I", 1),
    ]

    all_passed = True
    for instructor, expected_count in test_cases:
        cursor.execute("SELECT excellent_count FROM instructor_accolades WHERE instructor = ?", (instructor,))
        row = cursor.fetchone()
        if not row:
            print(f"FAIL: Instructor '{instructor}' was not found in instructor_accolades!")
            all_passed = False
        else:
            actual_count = row[0]
            if actual_count == expected_count:
                print(f"PASS: Instructor '{instructor}' has correct count {actual_count}.")
            else:
                print(f"FAIL: Instructor '{instructor}' has count {actual_count}, but expected {expected_count}!")
                all_passed = False

    # 4. Show some sample accolade records
    print("\nSample records from instructor_accolades:")
    cursor.execute("SELECT instructor, excellent_count FROM instructor_accolades ORDER BY excellent_count DESC LIMIT 10")
    rows = cursor.fetchall()
    for r in rows:
        print(f" - {r[0]}: {r[1]} semesters ranked as excellent")

    conn.close()
    return all_passed

if __name__ == "__main__":
    success = test_database_accolades()
    if success:
        print("\nAll database accolades tests PASSED successfully!")
    else:
        print("\nSome tests FAILED.")
