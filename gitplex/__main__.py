"""Main entry point for direct module execution."""

import sys
import logging
from pathlib import Path

from .cli import cli
from .exceptions import GitplexError
from .ui import print_error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / '.gitplex' / 'gitplex.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Main entry point."""
    try:
        # Ensure .gitplex directory exists
        gitplex_dir = Path.home() / '.gitplex'
        gitplex_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug("Starting GitPlex")
        cli()
    except GitplexError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error("Fatal error", exc_info=True)
        print_error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 