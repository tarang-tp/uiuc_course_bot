import sys
import os

# Insert bot directory to import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from bot import TRACKS_DATA
    # pyrefly: ignore [missing-import]
    import discord
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def test_tracks():
    print("Testing TRACKS_DATA structure and limits...")
    all_passed = True
    
    if not TRACKS_DATA:
        print("FAIL: TRACKS_DATA is empty!")
        return False
        
    print(f"Found {len(TRACKS_DATA)} curriculum tracks.")
    
    for name, data in TRACKS_DATA.items():
        print(f"\nAnalyzing track: '{name}'")
        
        # 1. Check schema keys
        if "description" not in data or "roadmap" not in data:
            print(f"FAIL: Missing 'description' or 'roadmap' key for track '{name}'")
            all_passed = False
            continue
            
        desc = data["description"]
        roadmap = data["roadmap"]
        
        # 2. Check description length (Discord Embed description limit is 4096)
        print(f" - Description length: {len(desc)} characters")
        if len(desc) > 2000:
            print(f"FAIL: Description too long ({len(desc)} > 2000)")
            all_passed = False
            
        # 3. Check roadmap length (Discord Embed field value limit is 1024)
        roadmap_str = f"```\n{roadmap}\n```"
        print(f" - Roadmap field value length: {len(roadmap_str)} characters")
        if len(roadmap_str) > 1024:
            print(f"FAIL: Roadmap exceeds Discord's 1024-character field limit ({len(roadmap_str)} > 1024)")
            all_passed = False
        else:
            print(" - PASS: Embed field limit compliance verified.")
            
        # 4. Print box drawing preview safely
        print("Roadmap Preview:")
        try:
            print(roadmap)
        except UnicodeEncodeError:
            enc = sys.stdout.encoding or 'ascii'
            print(roadmap.encode(enc, errors='replace').decode(enc))
        
    return all_passed

if __name__ == "__main__":
    success = test_tracks()
    if success:
        print("\nAll curriculum track tests PASSED successfully!")
        sys.exit(0)
    else:
        print("\nSome tests FAILED.")
        sys.exit(1)
