"""Command-line interface for the GRC pipeline."""

import click
import logging
from datetime import datetime
from pathlib import Path

from src.utils.logging_config import setup_logging, get_logger
from src.utils.date_utils import parse_date, get_week_key
from src.utils.config_loader import ConfigLoader
from src.api.auth import InbentaAuth
from src.api.signing import RequestSigner
from src.api.client import InbentaReportingClient
from src.api.editor_client import EditorAuth, InbentaEditorClient
from src.db.engine import DatabaseEngine
from src.ingestion.pipeline import IngestionPipeline
from src.transform.session_builder import SessionBuilder
from src.output.excel_writer import ExcelWriter


logger = get_logger(__name__)


def create_editor_client(config: ConfigLoader):
    """
    Create Editor API client if credentials are available.
    
    Args:
        config: Configuration loader
        
    Returns:
        InbentaEditorClient or None if credentials not configured
    """
    import os
    
    editor_key = os.getenv("INBENTA_EDITOR_API_KEY")
    editor_secret = os.getenv("INBENTA_EDITOR_API_SECRET")
    editor_personal_secret = os.getenv("INBENTA_EDITOR_PERSONAL_SECRET_KEY")
    
    if not all([editor_key, editor_secret, editor_personal_secret]):
        logger.warning("Editor API credentials not configured, content descriptions will not be fetched")
        logger.warning("Add INBENTA_EDITOR_API_KEY, INBENTA_EDITOR_API_SECRET, and INBENTA_EDITOR_PERSONAL_SECRET_KEY to .env")
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


@click.group()
@click.option("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
@click.option("--log-file", default=None, help="Path to log file (default: logs/grc_pipeline.log)")
def cli(log_level: str, log_file: str):
    """GRC Weekly Report Pipeline CLI."""
    setup_logging(log_level=log_level, log_file=log_file)


@cli.command()
@click.option("--date-from", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--date-to", required=True, help="End date (YYYY-MM-DD)")
@click.option("--report-num", required=True, type=int, help="Report number for filename")
def full_run(date_from: str, date_to: str, report_num: int):
    """Run the full pipeline: ingest, transform, and generate report."""
    logger.info("=" * 80)
    logger.info("FULL PIPELINE RUN")
    logger.info("=" * 80)
    
    try:
        start_date = parse_date(date_from)
        end_date = parse_date(date_to)
        week_key = get_week_key(start_date)
        
        logger.info(f"Date range: {date_from} to {date_to}")
        logger.info(f"Week key: {week_key}")
        logger.info(f"Report number: {report_num}")
        
        # Load configuration
        config = ConfigLoader()
        
        # Initialize components
        db_engine = DatabaseEngine(config.get('database.path'))
        db_engine.initialize_schema()
        
        api_config = config.get_api_config()
        auth = InbentaAuth(
            auth_url=api_config['auth_url'],
            api_key=api_config['key'],
            api_secret=api_config['secret'],
            refresh_buffer=api_config.get('token_refresh_buffer', 120)
        )
        # Use signature_key for HMAC signing (different from auth secret!)
        signer = RequestSigner(api_config['signature_key'])
        client = InbentaReportingClient(
            base_url=api_config['base_url'],
            auth=auth,
            signer=signer,
            rate_limit=api_config.get('rate_limit', 800)
        )
        
        filters_config = config.get_filters_config()
        
        # Step 1: Ingest
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: INGESTION")
        logger.info("=" * 80)
        
        ingestion = IngestionPipeline(
            client=client,
            db_engine=db_engine,
            included_sources=filters_config.get('sources', []),
            environment=filters_config.get('environment', 'production')
        )
        
        record_counts = ingestion.run(start_date, end_date, week_key)
        
        # Step 2: Transform
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: TRANSFORMATION")
        logger.info("=" * 80)
        
        # Initialize Editor API client for content resolution
        editor_client = create_editor_client(config)
        
        with db_engine.get_connection_context() as conn:
            builder = SessionBuilder(conn, editor_client=editor_client)
            report_rows = builder.build_report_rows(week_key)
        
        logger.info(f"Built {len(report_rows)} report rows")
        
        # Step 3: Generate report
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: REPORT GENERATION")
        logger.info("=" * 80)
        
        output_config = config.get_output_config()
        writer = ExcelWriter(output_config.get('report_dir', 'data/reports'))
        
        filepath = writer.write_report(
            rows=report_rows,
            date_from=start_date,
            date_to=end_date,
            report_num=report_num
        )
        
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Report saved to: {filepath}")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise click.ClickException(str(e))


@cli.command()
@click.option("--date-from", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--date-to", required=True, help="End date (YYYY-MM-DD)")
def ingest(date_from: str, date_to: str):
    """Ingest data from Inbenta API into database."""
    logger.info("Starting data ingestion")
    
    try:
        start_date = parse_date(date_from)
        end_date = parse_date(date_to)
        week_key = get_week_key(start_date)
        
        logger.info(f"Date range: {date_from} to {date_to}")
        logger.info(f"Week key: {week_key}")
        
        # Load configuration
        config = ConfigLoader()
        
        # Initialize components
        db_engine = DatabaseEngine(config.get('database.path'))
        db_engine.initialize_schema()
        
        api_config = config.get_api_config()
        auth = InbentaAuth(
            auth_url=api_config['auth_url'],
            api_key=api_config['key'],
            api_secret=api_config['secret']
        )
        # Use signature_key for HMAC signing (different from auth secret!)
        signer = RequestSigner(api_config['signature_key'])
        client = InbentaReportingClient(
            base_url=api_config['base_url'],
            auth=auth,
            signer=signer,
            rate_limit=api_config.get('rate_limit', 800)
        )
        
        filters_config = config.get_filters_config()
        
        ingestion = IngestionPipeline(
            client=client,
            db_engine=db_engine,
            included_sources=filters_config.get('sources', []),
            environment=filters_config.get('environment', 'production')
        )
        
        record_counts = ingestion.run(start_date, end_date, week_key)
        
        logger.info("Ingestion completed")
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise click.ClickException(str(e))


@cli.command()
@click.option("--week-key", required=True, help="Week key (e.g., 2026-W04)")
def transform(week_key: str):
    """Transform ingested data into report format."""
    logger.info(f"Starting transformation for week {week_key}")
    
    try:
        # Load configuration
        config = ConfigLoader()
        
        # Initialize database
        db_engine = DatabaseEngine(config.get('database.path'))
        
        # Initialize Editor API client for content resolution
        editor_client = create_editor_client(config)
        
        # Build report rows
        with db_engine.get_connection_context() as conn:
            builder = SessionBuilder(conn, editor_client=editor_client)
            report_rows = builder.build_report_rows(week_key)
        
        logger.info(f"Transformation completed: {len(report_rows)} rows")
        
    except Exception as e:
        logger.error(f"Transformation failed: {e}", exc_info=True)
        raise click.ClickException(str(e))


@cli.command()
@click.option("--week-key", required=True, help="Week key (e.g., 2026-W04)")
@click.option("--report-num", required=True, type=int, help="Report number for filename")
@click.option("--date-from", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--date-to", required=True, help="End date (YYYY-MM-DD)")
def generate_report(week_key: str, report_num: int, date_from: str, date_to: str):
    """Generate Excel report from transformed data."""
    logger.info(f"Generating report for week {week_key}, report number {report_num}")
    
    try:
        start_date = parse_date(date_from)
        end_date = parse_date(date_to)
        
        # Load configuration
        config = ConfigLoader()
        
        # Initialize database
        db_engine = DatabaseEngine(config.get('database.path'))
        
        # Initialize Editor API client for content resolution
        editor_client = create_editor_client(config)
        
        # Build report rows
        with db_engine.get_connection_context() as conn:
            builder = SessionBuilder(conn, editor_client=editor_client)
            report_rows = builder.build_report_rows(week_key)
        
        # Generate Excel file
        output_config = config.get_output_config()
        writer = ExcelWriter(output_config.get('report_dir', 'data/reports'))
        
        filepath = writer.write_report(
            rows=report_rows,
            date_from=start_date,
            date_to=end_date,
            report_num=report_num
        )
        
        logger.info(f"Report generated successfully: {filepath}")
        
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        raise click.ClickException(str(e))


@cli.command()
def list_sources():
    """List all sources and their exclusion status."""
    logger.info("Listing sources")
    
    try:
        # Load configuration
        config = ConfigLoader()
        
        # Initialize database
        db_engine = DatabaseEngine(config.get('database.path'))
        
        # Get available weeks
        weeks = db_engine.get_available_weeks()
        
        if not weeks:
            click.echo("No data available. Run ingestion first.")
            return
        
        # Use most recent week
        week_key = weeks[0]
        click.echo(f"\nSources for week {week_key}:")
        click.echo("=" * 80)
        
        with db_engine.get_connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, is_excluded
                FROM event_sources
                WHERE week_key = ?
                ORDER BY name
            """, (week_key,))
            
            allowed = []
            excluded = []
            
            for row in cursor.fetchall():
                name = row[0]
                is_excluded = row[1]
                
                if is_excluded:
                    excluded.append(name)
                else:
                    allowed.append(name)
            
            click.echo(f"\n✓ Allowed sources ({len(allowed)}):")
            for name in allowed:
                click.echo(f"  - {name}")
            
            click.echo(f"\n✗ Excluded sources ({len(excluded)}):")
            for name in excluded:
                click.echo(f"  - {name}")
        
    except Exception as e:
        logger.error(f"Failed to list sources: {e}", exc_info=True)
        raise click.ClickException(str(e))


@cli.command()
def list_weeks():
    """List available weeks in database."""
    logger.info("Listing available weeks")
    
    try:
        # Load configuration
        config = ConfigLoader()
        
        # Initialize database
        db_engine = DatabaseEngine(config.get('database.path'))
        
        # Get available weeks
        weeks = db_engine.get_available_weeks()
        
        if not weeks:
            click.echo("No data available. Run ingestion first.")
            return
        
        click.echo("\nAvailable weeks:")
        click.echo("=" * 80)
        
        with db_engine.get_connection_context() as conn:
            cursor = conn.cursor()
            
            for week_key in weeks:
                # Get session count for this week
                cursor.execute("""
                    SELECT COUNT(*) FROM agg_session_details WHERE week_key = ?
                """, (week_key,))
                
                session_count = cursor.fetchone()[0]
                
                click.echo(f"{week_key}: {session_count} sessions")
        
    except Exception as e:
        logger.error(f"Failed to list weeks: {e}", exc_info=True)
        raise click.ClickException(str(e))


if __name__ == "__main__":
    cli()
