"""GRC Weekly Report Dashboard - Simple Streamlit interface."""

import streamlit as st
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
import traceback

from webapp.utils.ui_helpers import run_pipeline, get_recent_reports, get_available_sources


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_dates(start_date: date, end_date: date) -> tuple[bool, str]:
    """
    Validate date selections.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    today = date.today()
    
    # Check future dates
    if start_date > today:
        return False, "Start date cannot be in the future"
    if end_date > today:
        return False, "End date cannot be in the future"
    
    # Check date order
    if start_date > end_date:
        return False, "End date must be on or after start date"
    
    # Check range (optional - warn if too large)
    days_diff = (end_date - start_date).days
    if days_diff > 31:
        return False, "Date range should not exceed 31 days"
    
    return True, ""


def main():
    """Main dashboard application."""
    
    # Page configuration
    st.set_page_config(
        page_title="GRC Weekly Report Generator",
        page_icon="📊",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Title and description
    st.title("📊 GRC Weekly Report Generator")
    st.markdown("""
    Generate comprehensive GRC weekly reports from chatbot data.
    Select date range and sources to download an Excel report.
    """)
    
    st.divider()
    
    # === REPORT GENERATION SECTION ===
    st.subheader("Generate New Report")
    
    # Get available sources from config
    available_sources = get_available_sources()
    
    # Date inputs in two columns
    col1, col2 = st.columns(2)
    
    with col1:
        # Default to last week
        default_start = date.today() - timedelta(days=7)
        start_date = st.date_input(
            "Start Date",
            value=default_start,
            max_value=date.today(),
            help="Select the start date for the report"
        )
    
    with col2:
        default_end = date.today() - timedelta(days=1)
        end_date = st.date_input(
            "End Date",
            value=default_end,
            max_value=date.today(),
            help="Select the end date for the report"
        )
    
    # Source selection
    st.markdown("#### 📂 Select Sources")
    
    # "Select All" checkbox
    select_all = st.checkbox("Select All Sources", value=True)
    
    if select_all:
        selected_sources = available_sources
    else:
        selected_sources = st.multiselect(
            "Choose sources to include in the report",
            options=available_sources,
            default=[],
            help="Select at least one source. Use Ctrl/Cmd to select multiple."
        )
    
    # Show selected count
    if selected_sources:
        st.info(f"✓ {len(selected_sources)} source(s) selected")
    else:
        st.warning("⚠️ Please select at least one source")
    
    # Validate dates
    is_valid, error_msg = validate_dates(start_date, end_date)
    
    if not is_valid:
        st.error(f"❌ {error_msg}")
    
    # Check if sources are selected
    sources_valid = len(selected_sources) > 0
    if not sources_valid and not select_all:
        st.error("❌ At least one source must be selected")
    
    # Generate button
    generate_button = st.button(
        "🚀 Generate Report",
        type="primary",
        disabled=not (is_valid and sources_valid),
        use_container_width=True
    )
    
    # Handle generation
    if generate_button:
        try:
            # Convert date to datetime for pipeline
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            
            # Progress container
            progress_container = st.container()
            status_text = progress_container.empty()
            progress_bar = progress_container.progress(0)
            
            # Track progress steps
            total_steps = 5
            current_step = [0]  # Use list to allow modification in callback
            
            def update_progress(msg: str):
                """Update progress display."""
                current_step[0] += 1
                progress = min(current_step[0] / total_steps, 1.0)
                status_text.info(f"⏳ {msg}")
                progress_bar.progress(progress)
            
            # Run the pipeline
            result = run_pipeline(
                start_date=start_dt,
                end_date=end_dt,
                selected_sources=selected_sources,
                progress_callback=update_progress
            )
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Success message
            st.success(f"✅ Report generated successfully: **{result['filename']}**")
            
            # Show summary
            with st.expander("📊 Report Summary", expanded=True):
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Total Rows", result['row_count'])
                col_b.metric("Week Key", result['week_key'])
                col_c.metric("Records", sum(result['record_counts'].values()))
            
            # Download button
            with open(result['filepath'], 'rb') as file:
                st.download_button(
                    label="⬇️ Download Excel Report",
                    data=file,
                    file_name=result['filename'],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            
        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}", exc_info=True)
            st.error(f"❌ Error generating report: {str(e)}")
            
            # Show detailed error in expander
            with st.expander("🔍 Error Details"):
                st.code(traceback.format_exc())
    
    st.divider()
    
    # === RECENT REPORTS SECTION ===
    st.subheader("📁 Recent Reports")
    
    try:
        recent_reports = get_recent_reports(limit=10)
        
        if recent_reports:
            for report in recent_reports:
                with st.container():
                    col_name, col_info, col_download = st.columns([3, 2, 1])
                    
                    with col_name:
                        st.write(f"**{report['name']}**")
                    
                    with col_info:
                        st.caption(f"{report['size_mb']} MB • {report['modified']}")
                    
                    with col_download:
                        with open(report['path'], 'rb') as file:
                            st.download_button(
                                label="⬇️",
                                data=file,
                                file_name=report['name'],
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_{report['name']}"
                            )
        else:
            st.info("No reports found. Generate your first report above!")
            
    except Exception as e:
        logger.error(f"Error loading recent reports: {str(e)}")
        st.warning("Could not load recent reports")
    
    st.divider()
    
    # === FOOTER ===
    st.caption("💡 **Tip**: Reports are saved to `data/reports/` directory")


if __name__ == "__main__":
    main()
