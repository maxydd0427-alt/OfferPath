import argparse
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import configure_logging, get_logger, log_event
from app.db import SessionLocal, init_db
from app.models import AnalysisJob, JobStatus
from app.services.analysis import run_mock_analysis

logger = get_logger(__name__)


def process_next_queued_job(db: Session) -> int | None:
    job = db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.status == JobStatus.queued)
        .order_by(AnalysisJob.created_at)
    )
    if job is None:
        return None

    job_id = job.id
    log_event(logger, logging.INFO, "worker.job_claimed", job_id=job_id)
    run_mock_analysis(db, job_id)
    return job_id


def run_worker(poll_interval_seconds: float, once: bool) -> None:
    configure_logging()
    init_db()
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        once=once,
        poll_interval_seconds=poll_interval_seconds,
    )
    while True:
        db = SessionLocal()
        try:
            processed_job_id = process_next_queued_job(db)
        finally:
            db.close()

        if processed_job_id is not None:
            log_event(logger, logging.INFO, "worker.job_processed", job_id=processed_job_id)
        elif once:
            log_event(logger, logging.INFO, "worker.no_queued_jobs")
            return

        if once:
            return
        time.sleep(poll_interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OfferPath analysis worker.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one queued job and then exit.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=5.0,
        help="Seconds to wait between queue checks when running continuously.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_worker(
        poll_interval_seconds=args.poll_interval_seconds,
        once=args.once,
    )


if __name__ == "__main__":
    main()
