import sqlite3
import os

def check_db_integrity():
    db_path = "uiuc_bot.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist. Run build_db.py first.")
        return False
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Verify table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gpa_stats'")
    if not cursor.fetchone():
        print("FAIL: gpa_stats table does not exist!")
        conn.close()
        return False
    print("PASS: gpa_stats table exists.")
    
    # 2. Check cross-listed course MATH 450, CS 450, ECE 491, CSE 401
    target_rubrics = ['CS 450', 'MATH 450', 'ECE 491', 'CSE 401']
    print(f"\nChecking cross-listed rubrics: {target_rubrics}")
    
    # Let's query stats for these rubrics
    rubric_data = {}
    for rubric in target_rubrics:
        cursor.execute("""
            SELECT instructor, ap, a, am, bp, b, bm, cp, c, cm, dp, d, dm, f, w, average_gpa, total_graded
            FROM gpa_stats
            WHERE course_id = ?
            ORDER BY instructor
        """, (rubric,))
        rows = cursor.fetchall()
        rubric_data[rubric] = [dict(r) for r in rows]
        
    # Check that they all have records
    all_have_records = True
    for rubric, data in rubric_data.items():
        print(f" - {rubric} has {len(data)} instructor records.")
        if len(data) == 0:
            print(f"FAIL: {rubric} has no records in database!")
            all_have_records = False
            
    if not all_have_records:
        conn.close()
        return False
        
    # Check if they are all identical
    # Compare each other rubric to CS 450
    ref_rubric = 'CS 450'
    ref_data = rubric_data[ref_rubric]
    
    all_identical = True
    for rubric in target_rubrics:
        if rubric == ref_rubric:
            continue
            
        data = rubric_data[rubric]
        if len(data) != len(ref_data):
            print(f"FAIL: Record counts differ. {ref_rubric} has {len(ref_data)}, {rubric} has {len(data)}")
            all_identical = False
            continue
            
        for i in range(len(ref_data)):
            r_row = ref_data[i]
            m_row = data[i]
            if r_row['instructor'] != m_row['instructor']:
                print(f"FAIL: Instructor mismatch at index {i}: {r_row['instructor']} vs {m_row['instructor']}")
                all_identical = False
                break
                
            # Compare all numeric columns
            mismatched_cols = []
            for col in ['ap', 'a', 'am', 'bp', 'b', 'bm', 'cp', 'c', 'cm', 'dp', 'd', 'dm', 'f', 'w', 'average_gpa', 'total_graded']:
                if r_row[col] != m_row[col]:
                    mismatched_cols.append((col, r_row[col], m_row[col]))
                    
            if mismatched_cols:
                print(f"FAIL: Grade distribution mismatch for '{r_row['instructor']}' between {ref_rubric} and {rubric} on columns:")
                for col, val1, val2 in mismatched_cols:
                    print(f"   - {col}: {val1} vs {val2}")
                all_identical = False
                break
                
    if all_identical:
        print("PASS: All cross-listed rubrics have identical combined data and GPA metrics!")
    else:
        print("FAIL: Cross-listed course data is not identical.")
        
    # 3. Check some sample records
    print("\nSample records for 'CS 450':")
    cursor.execute("""
        SELECT instructor, average_gpa, total_graded
        FROM gpa_stats
        WHERE course_id = 'CS 450'
        ORDER BY total_graded DESC
    """)
    rows = cursor.fetchall()
    for row in rows[:5]:
        print(f" - {row['instructor']}: Avg GPA {row['average_gpa']:.2f} ({row['total_graded']:,} graded)")
        
    conn.close()
    return all_identical

if __name__ == "__main__":
    success = check_db_integrity()
    if success:
        print("\nAll integrity tests PASSED successfully!")
    else:
        print("\nSome integrity tests FAILED.")
