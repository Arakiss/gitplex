"""Main entry point for direct module execution."""

import sys
import logging
from .cli import cli

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Main entry point."""
    try:
        logger.debug("Starting GitPlex from __main__")
        cli()
    except Exception as e:
        logger.error("Fatal error", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 