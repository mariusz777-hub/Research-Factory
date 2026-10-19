from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from .models import Job


TERMINAL = {"SUCCESS", "FAILED"}
READY = {"QUEUED", "RETRY"}


def now_utc() -> datetime:
    return datetime.now(UTC)


class JobQueue:
    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        retry_base_seconds: int = 5,
        retry_max_seconds: int = 300,
    ):
        self.session_factory = session_factory
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds

    def recover_stale(self) -> int:
        now = now_utc()
        with self.session_factory.begin() as session:
            jobs = list(
                session.scalars(
                    select(Job).where(Job.status == "RUNNING", Job.leased_until < now)
                )
            )
            for job in jobs:
                if job.attempts >= job.max_attempts:
                    job.status = "FAILED"
                    job.last_error = (job.last_error + " | " if job.last_error else "") + "Wygasła dzierżawa zadania."
                else:
                    job.status = "RETRY"
                    job.next_attempt_at = now
                job.leased_until = None
                job.worker_id = None
            return len(jobs)

    def claim_next(self, worker_id: str, lease_seconds: int) -> Job | None:
        now = now_utc()
        with self.session_factory.begin() as session:
            stmt = (
                select(Job)
                .where(
                    Job.status.in_(READY),
                    Job.next_attempt_at <= now,
                    or_(Job.leased_until.is_(None), Job.leased_until < now),
                )
                .order_by(Job.priority.asc(), Job.next_attempt_at.asc(), Job.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            job = session.scalar(stmt)
            if job is None:
                return None
            job.status = "RUNNING"
            job.attempts += 1
            job.worker_id = worker_id
            job.leased_until = now + timedelta(seconds=lease_seconds)
            job.last_error = ""
            session.flush()
            session.expunge(job)
            return job

    def mark_success(self, job_id: str, result_path: str = "") -> None:
        with self.session_factory.begin() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise KeyError(job_id)
            job.status = "SUCCESS"
            job.result_path = result_path
            job.leased_until = None
            job.worker_id = None

    def mark_failure(self, job_id: str, error: str, *, retryable: bool = True) -> str:
        now = now_utc()
        with self.session_factory.begin() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise KeyError(job_id)
            job.last_error = error[:12000]
            job.leased_until = None
            job.worker_id = None
            if retryable and job.attempts < job.max_attempts:
                delay = min(
                    self.retry_max_seconds,
                    self.retry_base_seconds * (2 ** max(0, job.attempts - 1)),
                )
                jitter = random.uniform(0, max(0.25, delay * 0.15))
                job.next_attempt_at = now + timedelta(seconds=delay + jitter)
                job.status = "RETRY"
            else:
                job.status = "FAILED"
            return job.status

    def heartbeat(self, job_id: str, lease_seconds: int) -> None:
        with self.session_factory.begin() as session:
            session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "RUNNING")
                .values(leased_until=now_utc() + timedelta(seconds=lease_seconds))
            )

    def get(self, job_id: str) -> Job | None:
        with self.session_factory() as session:
            return session.get(Job, job_id)
