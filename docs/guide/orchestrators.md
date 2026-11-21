# Orchestrators

masoora does not schedule, retry, alert, or backfill. Orchestrators are good at
those, so use one. masoora holds the pipeline logic and runs when called.

## The split

| Orchestrator | masoora |
|---|---|
| when a job runs | what the job does |
| retries, alerting, backfills | step order, data passing, parallelism |
| infrastructure | transformations |

A masoora pipeline runs as **one orchestrator task**. It does not expand into
one task per step. Steps are an implementation detail of your job, and the
orchestrator does not need to know about them.

## Package the pipeline

Put your pipelines in their own package and publish it to whatever index you
already use.

```python
# my_pipelines/daily_events.py
from masoora import Pipeline, PipelineBuilder, PipelineContext


class DailyEventsContext(PipelineContext):
    run_date: str
    source_url: str
    min_score: float = 0.5


def build() -> Pipeline[DailyEventsContext]:
    return (
        PipelineBuilder[DailyEventsContext]()
        .with_read_step(read_events, output="events")
        .with_transform_step(score, inputs=["events"], output="scored")
        .with_write_step(write_db, inputs=["scored"])
        .build()
    )
```

Ship it as a versioned wheel: `my-pipelines==2.3.0`.

## Call it from a DAG

```python
# airflow/dags/daily_events.py
from airflow.decorators import dag, task
from my_pipelines.daily_events import DailyEventsContext, build


@dag(schedule="@daily", params={"source_url": "s3://events/", "min_score": 0.5})
def daily_events():
    @task
    def run(**kwargs):
        ctx = DailyEventsContext(
            run_date=kwargs["ds"],
            **kwargs["params"],
        )
        build().run(ctx, parallel=True)

    run()


daily_events()
```

The DAG file stays small. It says when to run and what parameters to pass.
Everything else lives in the versioned package.

## Without an orchestrator

You do not need Airflow to run a pipeline. If your scheduler is cron, a Cloud
Run Job, a Kubernetes CronJob, or a button on your laptop, the pattern is the
same: a small command-line entry point builds the context from its arguments,
runs the pipeline, and exits non-zero on failure. The scheduler supplies the
schedule and the retries; the process exit code is the whole contract.

```python
# my_pipelines/cli.py
import typer

from masoora import StepExecutionError
from my_pipelines.daily_events import DailyEventsContext, build


def main(run_date: str, source_url: str, min_score: float = 0.5) -> None:
    """Run the daily events pipeline for one date."""
    ctx = DailyEventsContext(run_date=run_date, source_url=source_url, min_score=min_score)
    try:
        catalog = build().run(ctx, parallel=True)
    except StepExecutionError as exc:
        typer.echo(f"{exc.step_name} failed: {exc.original!r}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"scored={len(catalog['scored'])}")


def cli() -> None:
    typer.run(main)


if __name__ == "__main__":
    cli()
```

The command line is validated by Pydantic exactly as Airflow's params are: a bad
`run_date` fails before any data is read. For how to unwrap the error and why
the exit code matters, see [Errors and retries](errors.md#turning-it-into-a-non-zero-exit).
Declare the script in your package's `pyproject.toml` so installing the wheel
gives you a command:

```toml
[project.scripts]
daily-events = "my_pipelines.cli:cli"
```

Typer is not a masoora dependency; add it to your own package's dependencies, or
use `argparse` and `sys.exit(1)` if you would rather not.

### Cron

```cron
0 2 * * *  daily-events "$(date +\%F)" s3://events/ >> /var/log/daily-events.log 2>&1
```

### Cloud Run Jobs and other containers

Install the pinned wheel in the image and make the command the entry point
(the names below are placeholders for your own). The job runs to completion and the platform reads the exit code: zero is
success, non-zero marks the execution failed and triggers the job's own retry
setting.

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir "my-pipelines==2.3.0"
ENTRYPOINT ["daily-events"]
```

```bash
gcloud run jobs create daily-events \
  --image europe-docker.pkg.dev/my-project/jobs/daily-events:2.3.0 \
  --args="2026-01-31,s3://events/" \
  --max-retries=2
```

Because the platform may retry a failed execution, the writes in the pipeline
must be safe to run again — see
[Designing writes for failure](errors.md#designing-writes-for-failure).

## Why this is worth doing

**You can change the pipeline without deploying the orchestrator.** Bump
`my-pipelines` to 2.4.0 and the next run picks it up. Airflow deployments are
slow and shared; package releases are fast and yours.

**You know what ran.** The version in the DAG is the version that executed. To
reproduce a run from three weeks ago, install that version.

**You can roll back in one line.** Pin the previous version.

**You can test it properly.** Testing inside an orchestrator is painful.
Testing a package is `pytest`. See [Testing](testing.md).

**You can run it anywhere.** The same wheel runs on your laptop, in CI, and in
production, with no orchestrator involved.

## Parameters become the context

The context is where the orchestrator hands off. Params, Variables, and
`dag_run.conf` arrive as untrusted dictionaries; Pydantic validates them once,
at the boundary.

```python
ctx = DailyEventsContext(run_date=kwargs["ds"], **kwargs["params"])
```

A missing or misspelled parameter fails immediately, with a message naming the
field, before any data is read.

!!! tip "Pin your pipelines package"

    Use `my-pipelines==2.3.0`, not `my-pipelines>=2.3`. A floating version
    means a scheduled run can change behaviour without anyone deploying
    anything, which is a bad surprise at 3am.

## Other runners

Nothing here is Airflow-specific. `pipeline.run(ctx)` is an ordinary function
call, so the same package works under Dagster, Prefect, cron, a container job,
or a notebook.

If you want a command-line entry point for your pipelines, add one in your own
package — masoora does not ship a CLI, since the right arguments and defaults
depend on your pipelines rather than on masoora.
