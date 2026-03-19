"""UI helper functions for the dashboard."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import os
from src.utils.config_loader import ConfigLoader
from src.db.engine import DatabaseEngine
from src.api.auth import InbentaAuth
from src.api.signing import RequestSigner
from src.api.client import InbentaReportingClient
from src.api.editor_client import EditorAuth, InbentaEditorClient
from src.ingestion.pipeline import IngestionPipeline
from src.transform.session_builder import SessionBuilder
from src.output.excel_writer import ExcelWriter
from src.utils.date_utils import get_week_key

logger = logging.getLogger(__name__)


def _create_editor_client():
    """
    Create Editor API client if credentials are available.
    
    Returns:
        InbentaEditorClient or None if credentials not configured
    """
    editor_key = os.getenv("INBENTA_EDITOR_API_KEY")
    editor_secret = os.getenv("INBENTA_EDITOR_API_SECRET")
    editor_personal_secret = os.getenv("INBENTA_EDITOR_PERSONAL_SECRET_KEY")
    
    if not all([editor_key, editor_secret, editor_personal_secret]):
        logger.warning("Editor API credentials not configured, content titles will use placeholders")
        return None
    
    try:
        auth = EditorAuth(
            auth_url="https://api.inbenta.io/v1/auth",
            api_key=editor_key,
            api_secret=editor_secret,
            user_personal_secret=editor_personal_secret
        )
        
        editor_base_url = os.getenv("INBENTA_EDITOR_BASE_URL", "https://chatbot-api-us.inbenta.io/editor/v1")
        
        client = InbentaEditorClient(
            base_url=editor_base_url,
            auth=auth,
            rate_limit=100
        )
        
        logger.info("Editor API client initialized successfully")
        return client
        
    except Exception as e:
        logger.error(f"Failed to initialize Editor API client: {e}")
        return None


def get_available_sources() -> list[str]:
    """
    Get list of available sources from config.
    
    Returns:
        List of source names from config
    """
    try:
        config = ConfigLoader()
        filters_config = config.get_filters_config()
        sources = filters_config.get('sources', [])
        return sources
    except Exception as e:
        logger.error(f"Failed to load sources from config: {e}")
        return []


def run_pipeline(
    start_date: datetime, 
    end_date: datetime,
    selected_sources: list[str],
    progress_callback=None
) -> Dict[str, Any]:
    """
    Run the full GRC pipeline and return result info.
    
    This wraps the existing CLI logic but returns data instead of printing.
    It reuses all existing code - no duplication!
    
    Args:
        start_date: Start date for report
        end_date: End date for report
        selected_sources: List of sources to include in the report
        progress_callback: Optional callback function to update progress (message: str)
        
    Returns:
        Dict with:
            - filepath: Full path to generated Excel file
            - filename: Just the filename
            - row_count: Number of rows in report
            - week_key: Week key used
            - record_counts: Dict of record counts by table
            
    Raises:
        Exception: If any step fails
    """
    def update_progress(msg: str):
        """Helper to log and optionally call progress callback."""
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)
    
    try:
        # Load configuration
        update_progress("Loading configuration...")
        config = ConfigLoader()
        
        # Initialize database
        update_progress("Initializing database...")
        db_engine = DatabaseEngine(config.get('database.path'))
        db_engine.initialize_schema()
        
        # Generate week key
        week_key = get_week_key(start_date)
        update_progress(f"Using week key: {week_key}")
        
        # Initialize API components (exactly like CLI)
        update_progress("Authenticating with Inbenta API...")
        api_config = config.get_api_config()
        
        auth = InbentaAuth(
            auth_url=api_config['auth_url'],
            api_key=api_config['key'],
            api_secret=api_config['secret'],
            refresh_buffer=api_config.get('token_refresh_buffer', 120)
        )
        
        signer = RequestSigner(api_config['signature_key'])
        
        client = InbentaReportingClient(
            base_url=api_config['base_url'],
            auth=auth,
            signer=signer,
            rate_limit=api_config.get('rate_limit', 800)
        )
        
        # Get filters config
        filters_config = config.get_filters_config()
        
        # Step 1: Data Ingestion
        update_progress("Fetching data from Inbenta API...")
        ingestion = IngestionPipeline(
            client=client,
            db_engine=db_engine,
            included_sources=selected_sources,  # Use user-selected sources
            environment=filters_config.get('environment', 'production')
        )
        
        record_counts = ingestion.run(start_date, end_date, week_key)
        
        update_progress(f"Ingested {sum(record_counts.values())} total records")
        
        # Initialize Editor API client for content titles
        editor_client = _create_editor_client()
        
        # Step 2: Data Transformation
        update_progress("Building report rows...")
        with db_engine.get_connection_context() as conn:
            builder = SessionBuilder(conn, editor_client=editor_client)
            report_rows = builder.build_report_rows(week_key)
        
        update_progress(f"Built {len(report_rows)} report rows")
        
        # Step 3: Excel Generation
        update_progress("Generating Excel file...")
        output_config = config.get_output_config()
        writer = ExcelWriter(output_config.get('report_dir', 'data/reports'))
        
        # Generate simple filename: GRC Weekly report DDMMYYYY_DDMMYYYY.xlsx
        filename = f"GRC Weekly report {start_date.strftime('%d%m%Y')}_{end_date.strftime('%d%m%Y')}.xlsx"
        
        filepath = writer.write_report(
            rows=report_rows,
            date_from=start_date,
            date_to=end_date,
            custom_filename=filename
        )
        
        update_progress(f"Report generated: {Path(filepath).name}")
        
        return {
            'filepath': str(filepath),
            'filename': Path(filepath).name,
            'row_count': len(report_rows),
            'week_key': week_key,
            'record_counts': record_counts,
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        raise


def get_recent_reports(reports_dir: str = "data/reports", limit: int = 10) -> list:
    """
    Get list of recently generated reports.
    
    Args:
        reports_dir: Directory containing report files
        limit: Maximum number of reports to return
        
    Returns:
        List of dicts with report info (name, path, size, modified_time)
    """
    reports_path = Path(reports_dir)
    
    if not reports_path.exists():
        return []
    
    # Get all Excel files
    excel_files = list(reports_path.glob("*.xlsx"))
    
    # Sort by modification time (newest first)
    excel_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    # Build result list
    reports = []
    for filepath in excel_files[:limit]:
        stat = filepath.stat()
        reports.append({
            'name': filepath.name,
            'path': str(filepath),
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return reports
