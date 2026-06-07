import chart_gen

# Mock grade array representing:
# ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'W']
mock_grades = [10, 25, 15, 20, 30, 10, 5, 8, 4, 2, 1, 0, 3, 5]

try:
    chart_stream = chart_gen.generate_gpa_chart(mock_grades)
    with open("test_chart.png", "wb") as f:
        f.write(chart_stream.read())
    print("Success: test_chart.png generated successfully!")
except Exception as e:
    print(f"Error generating chart: {e}")
