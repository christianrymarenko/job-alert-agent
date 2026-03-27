from src.core.config import load_config
from src.core.logging_setup import setup_logging
from src.core.pipeline import run_scheduler


if __name__ == "__main__":
    cfg = load_config()
    setup_logging(cfg.log_level)
    run_scheduler(cfg)
