import logging
import warnings
from typing import Optional, Dict, List

DEFAULT_EXTERNAL_LIBS = ['pdf2image']
DEFAULT_WARNING_PATTERNS = [".*poppler.*", ".*Unable to get page count.*"]


class UserFriendlyFilter(logging.Filter):
    def __init__(self, friendly_messages: Optional[Dict[str, str]] = None):
        super().__init__()
        self.friendly_messages = friendly_messages or {}
    
    def filter(self, record):
        msg_lower = record.getMessage().lower()
        for technical_msg, friendly_msg in self.friendly_messages.items():
            if technical_msg.lower() in msg_lower:
                record.msg = friendly_msg
                record.levelno = logging.ERROR  # CKDEV-NOTE: Changed from INFO to ERROR
                record.levelname = 'ERROR'  # CKDEV-NOTE: Changed from INFO to ERROR
                break
        return True


def setup_user_friendly_logging(friendly_messages: Optional[Dict[str, str]] = None, 
                               external_libs: Optional[List[str]] = None):
    root_logger = logging.getLogger()
    filter_instance = UserFriendlyFilter(friendly_messages)
    
    for handler in root_logger.handlers:
        handler.filters.clear()
        handler.addFilter(filter_instance)
    
    libs_to_suppress = external_libs or DEFAULT_EXTERNAL_LIBS
    [logging.getLogger(lib).setLevel(logging.ERROR) for lib in libs_to_suppress]


def suppress_external_warnings(warning_patterns: Optional[List[str]] = None):
    patterns = warning_patterns or DEFAULT_WARNING_PATTERNS
    [warnings.filterwarnings("ignore", message=pattern) for pattern in patterns]


if __name__ != "__main__":
    setup_user_friendly_logging()
    suppress_external_warnings()