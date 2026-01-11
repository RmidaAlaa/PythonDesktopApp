import socket
import logging

logger = logging.getLogger(__name__)

def check_internet_connection(host="8.8.8.8", port=53, timeout=3):
    """
    Check if there is an internet connection by trying to connect to a reliable host.
    Default is Google DNS (8.8.8.8).
    """
    try:
        socket.setdefaulttimeout(timeout)
        # 8.8.8.8 is Google DNS, port 53 is DNS service. 
        # It's reliable and usually open.
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        logger.debug(f"Internet check failed: {ex}")
        return False
