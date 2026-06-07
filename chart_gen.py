import io
# pyrefly: ignore [missing-import]
import matplotlib
# Use Agg backend for headless systems (vital for running inside a bot/server without display)
matplotlib.use('Agg')
# pyrefly: ignore [missing-import]
import matplotlib.pyplot as plt
# pyrefly: ignore [missing-import]
import numpy as np

def generate_gpa_chart(grade_counts):
    """
    Generates a minimalist, transparent grade distribution bar chart matching the user's mockup.
    
    Args:
        grade_counts (list): List of counts corresponding to:
            ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'W']
            
    Returns:
        io.BytesIO: In-memory binary stream containing the PNG image.
    """
    grades = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'W']
    
    if len(grade_counts) != len(grades):
        raise ValueError(f"Expected {len(grades)} grade counts, got {len(grade_counts)}")
    
    # Calculate percentages
    total = sum(grade_counts)
    if total > 0:
        percentages = [(count / total) * 100 for count in grade_counts]
    else:
        percentages = [0.0] * len(grades)

    # Custom user-provided color codes for each grade
    colors = [
        '#3FAA59',  # A+
        '#6BBF64',  # A
        '#8ECF67',  # A-
        '#B1DE71',  # B+
        '#CFEB85',  # B
        '#E8F59F',  # B-
        '#FEFFBE',  # C+
        '#FEEFA3',  # C
        '#FEDA86',  # C-
        '#FDBD6D',  # D+
        '#FA9B58',  # D
        '#F57748',  # D-
        '#E75337',  # F
        '#D62F27'   # W
    ]

    # Global text color styling for matplotlib (muted gray for labels)
    plt.rcParams['text.color'] = '#d1d5db'
    plt.rcParams['xtick.color'] = '#d1d5db'
    plt.rcParams['font.family'] = 'sans-serif'
    
    # Create figure and axes with transparent background
    fig, ax = plt.subplots(figsize=(8.5, 3.5), facecolor='none')
    ax.set_facecolor('none')
    
    # Draw bars without visible border line, with a narrower width for more spacing
    bars = ax.bar(grades, percentages, color=colors, width=0.6, edgecolor='none')
    
    # Annotate integer percentage centered directly on top of each bar
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.annotate(f'{height:.0f}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 4),  # 4 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom',
                        color='#d1d5db', fontsize=9.5, fontweight='bold')
        else:
            bar.set_visible(False)
            
    # Set y-limit with extra room for annotations
    max_pct = max(percentages) if percentages else 0
    ax.set_ylim(0, max_pct * 1.15 if max_pct > 0 else 10)
    
    # Completely hide y-axis (ticks, tick labels, labels, grids)
    ax.yaxis.set_visible(False)
    
    # Remove all spines (top, right, left, and bottom)
    for spine in ax.spines.values():
        spine.set_visible(False)
        
    # Remove x-axis tick marks but keep the tick labels (A+, A, etc.)
    ax.tick_params(axis='x', length=0, labelsize=10, pad=8)
    
    # Adjust layout to fit everything nicely
    plt.tight_layout()
    
    # Save the figure into an in-memory BytesIO stream with transparent background
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', transparent=True, edgecolor='none')
    buf.seek(0)
    
    # Clean up to prevent memory leaks
    plt.close(fig)
    
    return buf
