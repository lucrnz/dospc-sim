# Batch Task Execution Guide

## Scope
This guide applies **only to files matching `*.tasks.md` in this directory**. Do not apply it to any other documentation in the repo.

A `.tasks.md` file is a list of work items sorted top-to-bottom by descending priority/complexity. Each item has a `Status` field. Work through the file in batches of two tasks.

## Selecting a Batch
1. Read the file from top to bottom.
2. Pick the first **2 tasks** whose `Status` is **not** `Done`, `In progress`, or `Ignore`.
3. These two tasks are the current batch. Process them in order.

## Per-Task Workflow
For each task in the batch:

### 1. Pre-task benchmark
- Run the project benchmark.
- Record the result inline under the task in a note titled `Benchmark data:`.
- Set the task to `Status: In progress`.

### 2. Execute the task
- While working, re-read the project root `AGENTS.md` and verify nothing it requires is being missed.

### 3. Post-task benchmark
- Run the benchmark again.
- Append the new result to the same `Benchmark data:` note, next to the pre-task value, and record the delta.
- Classify the change as one of: **improvement**, **regression**, or **noise**. If it is a regression, include the regression percentage.

### 4. Resolve the task status
- **If this is a performance task and the post-task benchmark shows a regression:** set `Status: Ignore`, add a brief note explaining the regression, and move on to the next task.
- **Otherwise:** set `Status: Done`.

## Per-Batch Workflow
Once both tasks in the batch are resolved (each either `Done` or `Ignore`):

1. Make a single git commit covering the batch.
2. Return to **Selecting a Batch** and process the next two eligible tasks.
3. Stop when no eligible tasks remain.
