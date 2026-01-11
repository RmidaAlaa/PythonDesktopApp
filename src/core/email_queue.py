import json
import logging
import uuid
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from .config import Config

logger = logging.getLogger("EmailQueue")

class EmailQueueManager:
    """Manages an offline email queue persisted to disk."""
    
    def __init__(self):
        self.queue_file = Config.APPDATA_DIR / "email_queue.json"
        self._queue: List[Dict[str, Any]] = []
        self.load_queue()

    def load_queue(self):
        """Load queue from disk."""
        try:
            if self.queue_file.exists():
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    self._queue = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load email queue: {e}")
            self._queue = []

    def save_queue(self):
        """Save queue to disk."""
        try:
            # Ensure directory exists
            self.queue_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(self._queue, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save email queue: {e}")

    def add_to_queue(self, email_data: Dict[str, Any]):
        """Add an email to the queue."""
        # Clean up Path objects for JSON serialization
        if "attachment_path" in email_data and isinstance(email_data["attachment_path"], Path):
            email_data["attachment_path"] = str(email_data["attachment_path"])
            
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            **email_data
        }
        
        self._queue.append(entry)
        self.save_queue()
        logger.info(f"Email queued. ID: {entry['id']}. Queue size: {len(self._queue)}")

    def get_pending_emails(self) -> List[Dict[str, Any]]:
        """Get all pending emails."""
        return self._queue

    def remove_from_queue(self, email_id: str):
        """Remove an email from the queue by ID."""
        self._queue = [e for e in self._queue if e["id"] != email_id]
        self.save_queue()
