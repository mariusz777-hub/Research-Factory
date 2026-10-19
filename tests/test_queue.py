from datetime import timedelta

from research_factory.models import Job, Project, Run
from research_factory.queue import JobQueue, now_utc


def seed(session_factory):
    with session_factory.begin() as session:
        project = Project(name="P", slug="p", idea="opis pomysłu dłuższy niż minimum", selected_models=["openai"], selected_scopes=[])
        run = Run(project=project)
        session.add_all([project, run])
        session.flush()
        job = Job(run_id=run.id, job_type="REPORT", dedupe_key="report", payload={}, max_attempts=2)
        session.add(job)
        session.flush()
        return job.id


def test_claim_retry_and_terminal_failure(session_factory):
    job_id = seed(session_factory)
    queue = JobQueue(session_factory, retry_base_seconds=1, retry_max_seconds=2)
    first = queue.claim_next("w1", 60)
    assert first.id == job_id and first.attempts == 1
    assert queue.mark_failure(job_id, "temporary", retryable=True) == "RETRY"
    with session_factory.begin() as session:
        job = session.get(Job, job_id)
        job.next_attempt_at = now_utc() - timedelta(seconds=1)
    second = queue.claim_next("w2", 60)
    assert second.attempts == 2
    assert queue.mark_failure(job_id, "still bad", retryable=True) == "FAILED"


def test_stale_lease_is_recovered(session_factory):
    job_id = seed(session_factory)
    queue = JobQueue(session_factory)
    queue.claim_next("dead-worker", 60)
    with session_factory.begin() as session:
        job = session.get(Job, job_id)
        job.leased_until = now_utc() - timedelta(seconds=1)
    assert queue.recover_stale() == 1
    with session_factory() as session:
        assert session.get(Job, job_id).status == "RETRY"
