"""Excel report generation."""

import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
try:
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
except Exception:
    import re
    ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]")

from .config import Config
from .device_detector import Device
from .logger import setup_logger

logger = setup_logger("ReportGenerator")


class ReportGenerator:
    """Generates Excel reports."""
    
    def __init__(self):
        self.logger = logger
        self._invalid_sheet_chars = set('[]:*?/\\')
    
    def generate_report(self, devices: List[Device], operator_info: Dict, 
                       machine_type: str, machine_id: str) -> Path:
        """Generate an Excel report."""
        workbook = Workbook()
        
        # Create metadata sheet
        self._create_metadata_sheet(workbook, operator_info)
        
        # Create devices sheet
        self._create_devices_sheet(workbook, devices, machine_type, machine_id)
        
        # Save file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"AWG_Kumulus_Report_{timestamp}.xlsx"
        report_path = Config.APPDATA_DIR / filename
        
        workbook.save(report_path)
        logger.info(f"Report saved to {report_path}")
        
        return report_path
    
    def _create_metadata_sheet(self, workbook: Workbook, operator_info: Dict):
        """Create the metadata sheet."""
        sheet = workbook.active
        sheet.title = self._safe_sheet_title("Metadata")
        
        # Get PC info
        pc_name = platform.node()
        pc_os = f"{platform.system()} {platform.release()}"
        
        headers = ["Property", "Value"]
        data = [
            ["Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["Application", "AWG Kumulus Device Manager"],
            ["Version", "1.0.0"],
            ["Operator Name", self._sanitize_cell_value(operator_info.get("name", "N/A"))],
            ["Operator Email", self._sanitize_cell_value(operator_info.get("email", "N/A"))],
            ["Client Name", self._sanitize_cell_value(operator_info.get("client_name", "N/A"))],
            ["Machine Type", self._sanitize_cell_value(operator_info.get("machine_type", "N/A"))],
            ["Machine ID", self._sanitize_cell_value(operator_info.get("machine_id", "N/A"))],
            ["PC Name", self._sanitize_cell_value(pc_name)],
            ["PC OS", self._sanitize_cell_value(pc_os)],
            ["Platform", self._sanitize_cell_value(platform.machine())],
        ]
        
        # Write headers
        for col, header in enumerate(headers, 1):
            cell = sheet.cell(1, col)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(bold=True, color="FFFFFF")
        
        # Write data
        for row, row_data in enumerate(data, 2):
            for col, value in enumerate(row_data, 1):
                sheet.cell(row, col, self._sanitize_cell_value(value))
        
        # Adjust column widths
        sheet.column_dimensions['A'].width = 20
        sheet.column_dimensions['B'].width = 40
    
    def _create_devices_sheet(self, workbook: Workbook, devices: List[Device], 
                             machine_type: str, machine_id: str):
        """Create the devices sheet."""
        sheet = workbook.create_sheet(title=self._safe_sheet_title("Devices"))
        
        headers = [
            "Machine Type", "Machine ID", "Board Type", "Port", 
            "VID", "PID", "UID", "Chip ID", "MAC Address", "Manufacturer", 
            "Serial Number", "Firmware Version", "Hardware Version", 
            "Flash Size", "CPU Frequency", "Timestamp"
        ]
        
        # Write headers
        for col, header in enumerate(headers, 1):
            cell = sheet.cell(1, col)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center")
        
        # Write device data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for row, device in enumerate(devices, 2):
            data = [
                self._sanitize_cell_value(machine_type),
                self._sanitize_cell_value(machine_id),
                self._sanitize_cell_value(device.board_type.value),
                self._sanitize_cell_value(device.port),
                self._sanitize_cell_value(f"0x{device.vid:04X}") if device.vid else "N/A",
                self._sanitize_cell_value(f"0x{device.pid:04X}") if device.pid else "N/A",
                self._sanitize_cell_value(device.uid or "N/A"),
                self._sanitize_cell_value(device.chip_id or "N/A"),
                self._sanitize_cell_value(device.mac_address or "N/A"),
                self._sanitize_cell_value(device.manufacturer or "N/A"),
                self._sanitize_cell_value(device.serial_number or "N/A"),
                self._sanitize_cell_value(device.firmware_version or "N/A"),
                self._sanitize_cell_value(device.hardware_version or "N/A"),
                self._sanitize_cell_value(device.flash_size or "N/A"),
                self._sanitize_cell_value(device.cpu_frequency or "N/A"),
                timestamp
            ]
            
            for col, value in enumerate(data, 1):
                sheet.cell(row, col, value)
        
        # Freeze top row
        sheet.freeze_panes = 'A2'
        
        # Adjust column widths
        column_widths = [15, 15, 12, 10, 10, 10, 20, 15, 18, 20, 20, 15, 15, 12, 12, 20]
        for i, width in enumerate(column_widths, 1):
            sheet.column_dimensions[get_column_letter(i)].width = width

    def _sanitize_cell_value(self, value):
        """Strip characters Excel refuses."""
        if value is None:
            return "N/A"
        text = str(value)
        text = ILLEGAL_CHARACTERS_RE.sub("", text)
        text = text.strip()
        return text or "N/A"

    def _safe_sheet_title(self, title: str, fallback: str = "Sheet") -> str:
        """Ensure sheet titles avoid forbidden characters and length issues."""
        raw = title or fallback
        cleaned = "".join(ch if ch not in self._invalid_sheet_chars else " " for ch in raw)
        cleaned = cleaned.strip() or fallback
        return cleaned[:31]

