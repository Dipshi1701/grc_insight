"""Ingestion pipeline orchestrator."""

import logging
import json
from datetime import datetime
from typing import Dict, Any

from src.api.client import InbentaReportingClient
from src.db.engine import DatabaseEngine
from src.db.repository import Repository
from src.ingestion.extractors import Extractors
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class IngestionPipeline:
    """Orchestrates the ingestion of data from API to database."""
    
    def __init__(
        self,
        client: InbentaReportingClient,
        db_engine: DatabaseEngine,
        included_sources: list[str],
        environment: str = "production"
    ):
        """
        Initialize ingestion pipeline.
        
        Args:
            client: API client
            db_engine: Database engine
            included_sources: List of sources to include (filter at API level)
            environment: Environment filter (default: production)
        """
        self.client = client
        self.db_engine = db_engine
        self.included_sources = included_sources
        self.environment = environment
        self.extractors = Extractors()
    
    def run(
        self,
        date_from: datetime,
        date_to: datetime,
        week_key: str
    ) -> Dict[str, int]:
        """
        Run the full ingestion pipeline.
        
        Args:
            date_from: Start date
            date_to: End date
            week_key: Week key for this data
            
        Returns:
            Dictionary of record counts per table
        """
        logger.info("=" * 80)
        logger.info(f"STARTING INGESTION: {week_key} ({date_from.date()} to {date_to.date()})")
        logger.info("=" * 80)
        
        start_time = datetime.now()
        record_counts = {}
        
        try:
            # Clear existing data for this week BEFORE opening main connection
            logger.info(f"Clearing existing data for {week_key}")
            self.db_engine.clear_week_data(week_key)
            
            with self.db_engine.get_connection_context() as conn:
                repo = Repository(conn)
                
                # Record ingestion start
                repo.record_ingestion_run(
                    week_key=week_key,
                    status="started",
                    start_time=start_time.isoformat()
                )
                
                # Step 1: Fetch reference data
                logger.info("\nStep 1: Fetching reference data")
                logger.info("-" * 80)
                
                # Use included sources from config for API filtering
                allowed_sources = self.included_sources if self.included_sources else None
                if allowed_sources:
                    logger.info(f"Filtering API calls to {len(allowed_sources)} sources: {', '.join(allowed_sources[:5])}{'...' if len(allowed_sources) > 5 else ''}")
                else:
                    logger.info("No source filter specified, fetching all sources")
                
                # Step 2: Fetch raw event data (starting with user questions)
                logger.info("\nStep 2: Fetching raw event data")
                logger.info("-" * 80)
                
                # User questions (fetch first)
                logger.info("Fetching user questions...")
                questions_raw = self.client.get_user_questions(
                    date_from=date_from,
                    date_to=date_to,
                    sources=allowed_sources if allowed_sources else None
                )
                
                questions, matchings = self.extractors.extract_user_questions(questions_raw)
                repo.bulk_insert_user_questions(questions, week_key)
                repo.bulk_insert_uq_matchings(matchings, week_key)
                record_counts['raw_user_questions'] = len(questions)
                record_counts['raw_uq_matchings'] = len(matchings)
                
                # Step 3: Fetch aggregated session details
                logger.info("\nStep 3: Fetching aggregated session details")
                logger.info("-" * 80)
                
                session_details_raw = self.client.get_session_details(
                    date_from=date_from,
                    date_to=date_to,
                    # environment=self.environment,
                    sources=allowed_sources if allowed_sources else None
                )
                
                session_details = self.extractors.extract_session_details(session_details_raw)
                repo.bulk_insert_session_details(session_details, week_key)
                record_counts['agg_session_details'] = len(session_details)
                
                # Sessions
                logger.info("\nFetching session events...")
                sessions_raw = self.client.get_sessions(
                    date_from=date_from,
                    date_to=date_to,
                    sources=allowed_sources if allowed_sources else None
                )
                
                # Filter sessions to keep only those with log_ids matching user questions
                logger.info("Filtering sessions by log_id...")
                valid_log_ids = set(q['event_id'] for q in questions)  # questions from earlier
                filtered_sessions = [
                    s for s in sessions_raw 
                    if s.get('log_id') and s.get('log_id') in valid_log_ids
                ]
                
                logger.info(f"Sessions before filtering: {len(sessions_raw)}")
                logger.info(f"Sessions after filtering: {len(filtered_sessions)}")
                logger.info(f"Filtered out: {len(sessions_raw) - len(filtered_sessions)} sessions")
                
                # Extract and insert filtered sessions
                sessions = self.extractors.extract_sessions(filtered_sessions)
                repo.bulk_insert_sessions(sessions, week_key)
                record_counts['raw_sessions'] = len(sessions)
                
                # Clicks
                logger.info("Fetching click events...")
                clicks_raw = self.client.get_clicks(
                    date_from=date_from,
                    date_to=date_to,
                    sources=allowed_sources if allowed_sources else None
                )
                
                clicks = self.extractors.extract_clicks(clicks_raw)
                repo.bulk_insert_clicks(clicks, week_key)
                record_counts['raw_clicks'] = len(clicks)
                
                # Ratings
                logger.info("Fetching rating events...")
                ratings_raw = self.client.get_ratings(
                    date_from=date_from,
                    date_to=date_to,
                    sources=allowed_sources if allowed_sources else None
                )
                
                ratings = self.extractors.extract_ratings(ratings_raw)
                repo.bulk_insert_ratings(ratings, week_key)
                record_counts['raw_ratings'] = len(ratings)
                
                # Record successful completion
                end_time = datetime.now()
                repo.record_ingestion_run(
                    week_key=week_key,
                    status="completed",
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                    record_counts=json.dumps(record_counts)
                )
            
            # Log summary
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("\n" + "=" * 80)
            logger.info("INGESTION COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            logger.info(f"Duration: {duration:.1f}s")
            logger.info("Record counts:")
            for table, count in record_counts.items():
                logger.info(f"  {table}: {count:,}")
            
            return record_counts
            
        except Exception as e:
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            
            # Record failure
            with self.db_engine.get_connection_context() as conn:
                repo = Repository(conn)
                repo.record_ingestion_run(
                    week_key=week_key,
                    status="failed",
                    start_time=start_time.isoformat(),
                    end_time=datetime.now().isoformat(),
                    error_message=str(e)
                )
            
            raise
