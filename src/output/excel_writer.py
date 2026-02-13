"""Excel report writer with formatting."""

import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from src.utils.logging_config import get_logger
from src.utils.date_utils import format_report_date

logger = get_logger(__name__)


class ExcelWriter:
    """Writes report data to formatted Excel file."""
    
    # Full 12 columns
    COLUMNS = [
        "Row Labels",
        "Count of User question",
        "Labels",
        "Source",
        "Category",
        "Classification",
        "Quality",
        "Answer available in the KB?",
        "Escalated Sessions",
        "Ratings assessment",
        "Date",
        "Time"
    ]
    
    # Column widths
    COLUMN_WIDTHS = {
        "Row Labels": 100,
        "Count of User question": 15,
        "Labels": 15,
        "Source": 20,
        "Category": 15,
        "Classification": 15,
        "Quality": 15,
        "Answer available in the KB?": 20,
        "Escalated Sessions": 18,
        "Ratings assessment": 18,
        "Date": 12,
        "Time": 10
    }
    
    # Blue background for session rows
    SESSION_FILL = PatternFill(start_color="D3E3F3", end_color="D3E3F3", fill_type="solid")
    
    def __init__(self, output_dir: str):
        """
        Initialize Excel writer.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def write_report(
        self,
        rows: List[Dict[str, Any]],
        date_from: datetime,
        date_to: datetime,
        report_num: int
    ) -> str:
        """
        Write report to Excel file.
        
        Args:
            rows: List of report row dictionaries
            date_from: Start date
            date_to: End date
            report_num: Report number
            
        Returns:
            Path to generated file
        """
        logger.info(f"Writing Excel report with {len(rows)} rows")
        
        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Report"
        
        # Write headers
        self._write_headers(ws)
        
        # Write data rows
        self._write_data(ws, rows)
        
        # Apply styling
        self._apply_styling(ws, len(rows))
        
        # Generate filename
        filename = self._generate_filename(date_from, date_to, report_num)
        filepath = self.output_dir / filename
        
        # Save workbook
        wb.save(filepath)
        
        logger.info(f"Report saved to: {filepath}")
        
        return str(filepath)
    
    def _write_headers(self, ws):
        """
        Write header row.
        
        Args:
            ws: Worksheet object
        """
        for col_idx, header in enumerate(self.COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="left", vertical="top")
    
    def _write_data(self, ws, rows: List[Dict[str, Any]]):
        """
        Write data rows.
        
        Args:
            ws: Worksheet object
            rows: List of report row dictionaries
        """
        for row_idx, row_data in enumerate(rows, start=2):
            # Column 1: Row Labels
            ws.cell(row=row_idx, column=1, value=row_data.get('row_label', ''))
            
            # Column 2: Count of User question
            ws.cell(row=row_idx, column=2, value=row_data.get('count', 1))
            
            # Column 3: Labels (Session/Question/Answer/Rating)
            ws.cell(row=row_idx, column=3, value=row_data.get('label_type', ''))
            
            # Column 4: Source
            ws.cell(row=row_idx, column=4, value=row_data.get('source', ''))
            
            # Column 5: Category (manual - leave empty)
            ws.cell(row=row_idx, column=5, value=row_data.get('category', ''))
            
            # Column 6: Classification (manual - leave empty)
            ws.cell(row=row_idx, column=6, value=row_data.get('classification', ''))
            
            # Column 7: Quality (manual - leave empty)
            ws.cell(row=row_idx, column=7, value=row_data.get('quality', ''))
            
            # Column 8: Answer available in the KB? (manual - leave empty)
            ws.cell(row=row_idx, column=8, value=row_data.get('answer_available', ''))
            
            # Column 9: Escalated Sessions (manual - leave empty)
            ws.cell(row=row_idx, column=9, value=row_data.get('escalated', ''))
            
            # Column 10: Ratings assessment (manual - leave empty)
            ws.cell(row=row_idx, column=10, value=row_data.get('ratings_assessment', ''))
            
            # Column 11: Date (only for Session rows)
            ws.cell(row=row_idx, column=11, value=row_data.get('date', ''))
            
            # Column 12: Time (only for Session rows)
            ws.cell(row=row_idx, column=12, value=row_data.get('time', ''))
            
            # Apply blue background to session rows
            if row_data.get('label_type') == 'Session':
                for col_idx in range(1, len(self.COLUMNS) + 1):
                    ws.cell(row=row_idx, column=col_idx).fill = self.SESSION_FILL
    
    def _apply_styling(self, ws, num_data_rows: int):
        """
        Apply styling to worksheet.
        
        Args:
            ws: Worksheet object
            num_data_rows: Number of data rows (excluding header)
        """
        # Set column widths
        for col_idx, header in enumerate(self.COLUMNS, start=1):
            col_letter = get_column_letter(col_idx)
            width = self.COLUMN_WIDTHS.get(header, 15)
            ws.column_dimensions[col_letter].width = width
        
        # Freeze header row
        ws.freeze_panes = "A2"
        
        # Enable auto-filter on headers
        ws.auto_filter.ref = f"A1:{get_column_letter(len(self.COLUMNS))}{num_data_rows + 1}"
        
        # Set alignment for all cells
        for row in ws.iter_rows(min_row=2, max_row=num_data_rows + 1, max_col=len(self.COLUMNS)):
            for cell in row:
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    
    def _generate_filename(self, date_from: datetime, date_to: datetime, report_num: int) -> str:
        """
        Generate filename for report.
        
        Format: {NN} GRC Weekly report {DDMMYYYY}_{DDMMYYYY}.xlsx
        
        Args:
            date_from: Start date
            date_to: End date
            report_num: Report number
            
        Returns:
            Filename string
        """
        date_from_str = format_report_date(date_from)
        date_to_str = format_report_date(date_to)
        
        filename = f"{report_num:02d} GRC Weekly report {date_from_str}_{date_to_str}.xlsx"
        
        return filename
