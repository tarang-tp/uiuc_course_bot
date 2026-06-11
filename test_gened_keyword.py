import sqlite3
import os

def test_gened_keyword_search():
    db_name = "uiuc_bot.db"
    if not os.path.exists(db_name):
        print(f"Error: {db_name} does not exist. Run build_db.py first.")
        return False

    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Define test queries for category and keyword combination
    tests = [
        # (category1, category2, min_gpa, keyword, expected_minimum_results)
        ("ACP", None, 3.0, "writing", 1),
        ("HUM", None, 3.4, "history", 1),
        ("NW", None, 3.2, "asia", 1),
        ("SBS", None, 3.0, "social", 1)
    ]

    category_map = {
        'ACP': '%advanced composition%',
        'WCC': '%cultural studies - western%',
        'NW': '%cultural studies - non-west%',
        'US': '%cultural studies - us minority%',
        'HUM': '%humanities%',
        'SBS': '%social & beh sci%',
        'NAT': '%nat sci & tech%'
    }

    all_passed = True
    for cat1, cat2, min_gpa, keyword, min_expected in tests:
        query = """
            SELECT c.course_id, c.title, g.average_gpa, c.credit_hours, c.degree_attributes
            FROM courses c
            JOIN gpa_stats g ON c.course_id = g.course_id
            WHERE g.instructor = 'ALL INSTRUCTORS COMBINED'
              AND g.average_gpa >= ?
              AND c.degree_attributes LIKE ?
        """
        params = [min_gpa, category_map[cat1]]

        if cat2:
            query += " AND c.degree_attributes LIKE ?"
            params.append(category_map[cat2])

        if keyword:
            query += " AND (c.title LIKE ? OR c.description LIKE ? OR c.course_id LIKE ?)"
            kw_pat = f"%{keyword}%"
            params.extend([kw_pat, kw_pat, kw_pat])

        query += " ORDER BY g.average_gpa DESC LIMIT 5"

        rows = cursor.execute(query, params).fetchall()
        print(f"\nQuerying: Category1={cat1}, Category2={cat2}, Keyword='{keyword}' (GPA >= {min_gpa})")
        print(f"Found {len(rows)} results:")
        for r in rows:
            print(f" - {r['course_id']}: {r['title']} (GPA: {r['average_gpa']:.2f})")

        if len(rows) < min_expected:
            print(f"FAIL: Expected at least {min_expected} results, got {len(rows)}")
            all_passed = False
        else:
            print("PASS")

    conn.close()
    return all_passed

if __name__ == "__main__":
    success = test_gened_keyword_search()
    if success:
        print("\nAll Gen-Ed keyword search tests PASSED successfully!")
    else:
        print("\nSome tests FAILED.")
