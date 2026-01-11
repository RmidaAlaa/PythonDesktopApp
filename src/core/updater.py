import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class AppUpdater:
    """Handles application update checks."""
    
    # Configuration
    GITHUB_REPO = "awg-kumulus/device-manager" # Placeholder
    
    def __init__(self):
        pass

    def check_for_updates(self, current_version: str) -> Optional[Dict[str, Any]]:
        """
        Check for updates.
        Returns None if no update, or dict with version info.
        """
        try:
            # Clean current version
            current_version = current_version.split('-')[0]
            
            # Real production update check
            url = f"https://api.github.com/repos/{self.GITHUB_REPO}/releases/latest"
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    latest_tag = data.get("tag_name", "").lstrip("v")
                    if self._is_newer(current_version, latest_tag):
                        # Find executable asset
                        download_url = ""
                        for asset in data.get("assets", []):
                            if asset.get("name", "").lower().endswith(".exe"):
                                download_url = asset.get("browser_download_url")
                                break
                        
                        return {
                            "version": latest_tag,
                            "url": data.get("html_url", ""),
                            "download_url": download_url,
                            "notes": data.get("body", "")
                        }
            except requests.RequestException as e:
                logger.warning(f"Failed to reach update server: {e}")
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return None

    def _is_newer(self, current: str, latest: str) -> bool:
        """Compare semantic versions."""
        try:
            c_parts = [int(x) for x in current.split('.')]
            l_parts = [int(x) for x in latest.split('.')]
            
            for i in range(max(len(c_parts), len(l_parts))):
                c = c_parts[i] if i < len(c_parts) else 0
                l = l_parts[i] if i < len(l_parts) else 0
                if l > c:
                    return True
                if l < c:
                    return False
            return False
        except Exception:
            return latest != current
