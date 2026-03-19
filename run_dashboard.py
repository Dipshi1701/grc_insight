"""Launch the GRC Dashboard.

Simple launcher script for the Streamlit dashboard.
Runs on http://localhost:8501
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Launch the Streamlit dashboard."""
    
    # Get the project root directory
    project_root = Path(__file__).parent
    dashboard_path = project_root / "webapp" / "dashboard.py"
    
    # Check if dashboard file exists
    if not dashboard_path.exists():
        print(f"Error: Dashboard file not found at {dashboard_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("Starting GRC Dashboard...")
    print("=" * 60)
    print()
    print("Dashboard URL: http://localhost:8501")
    print()
    print("Tips:")
    print("   - Open the URL above in your browser")
    print("   - Press Ctrl+C here to stop the dashboard")
    print("   - The dashboard will auto-reload when you edit files")
    print()
    print("=" * 60)
    print()
    
    try:
        # Run Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(dashboard_path),
            "--server.port=8501",
            "--server.address=localhost",
            "--server.headless=true",
            "--browser.gatherUsageStats=false"
        ])
    except KeyboardInterrupt:
        print("\n\nDashboard stopped.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
