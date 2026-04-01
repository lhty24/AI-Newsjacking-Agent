# Next Task Workflow

You are a task planner for the AI Newsjacking Agent project. Follow these steps in order:

## Step 1: Identify the Next Task

Read the Development Roadmap in `design-doc.md` (Section 7). Find all tasks with checkboxes (`- [ ]` and `- [x]`). Identify the first uncompleted task (`- [ ]`) in the current phase.

Cross-reference with recent git history (`git log --oneline -15`) to confirm what's actually been completed. If a task has been implemented but not checked off, mark it as complete (`- [x]`) in the design doc before moving on.

**Output**: State the task ID (e.g., P1-T1), its title, and which phase it belongs to.

## Step 2: Break Down the Task

If the task is non-trivial (more than a single file change):

- List the sub-tasks or components needed
- Identify which existing files will be modified and which new files need to be created
- Note any dependencies on existing code (read the relevant source files to confirm they exist and understand their APIs)
- Estimate relative complexity of each sub-task (small / medium / large)

Key directories and files to check for existing code and patterns:

- `src/models/` — Pydantic data models
- `src/modules/` — Pipeline modules (ingestion, analysis, generation, scoring, distribution)
- `src/api/` — FastAPI endpoints
- `src/pipeline.py` — Core pipeline orchestration (`run_pipeline`)
- `src/cli.py` — CLI entry point
- `src/config.py` — Configuration and environment variables
- `tests/` — Test files

Give a concise explanation for the sub-tasks/components breakdown.

**Output**: A numbered list of sub-tasks with files involved and complexity.

## Step 3: Create an Implementation Plan

For each sub-task, describe:

- Why we need this sub-task
- What to build and where
- Which existing functions/types/patterns to reuse (with file paths)
- How to test it

Reference the design doc (`design-doc.md`) for data model definitions, component specifications, and architectural decisions.

Give a concise explanation for the implementation plan.

**Output**: A concise, actionable plan organized by sub-task.

## Step 4: Ask for Permission

Present the full plan to the user and ask:

> Would you like to adjust or save the plan?

Do NOT save the plan or start implementation until the user explicitly approves. If the user requests edits, incorporate them and present the updated plan again for approval.

## Step 5: Save the Plan

Once the user approves, save the final implementation plan as a markdown file in `plans/` named after the task ID (e.g., `plans/P1-T1.md`). Create the directory if it does not exist.

## Step 6: Begin Implementation

Start implementing the first sub-task. After completing each sub-task, mark progress and move to the next one. When the entire task is complete, update the design doc roadmap to check off the task (`- [x]`).
