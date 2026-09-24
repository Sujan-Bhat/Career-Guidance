# OULAD Ingestion

[OULAD](https://analyse.kmi.open.ac.uk/open_dataset) (Open University Learning
Analytics Dataset) is the real-data component of the CAREERMIND data strategy.
Phase 1 ingests it into the CAREERMIND schema; the synthetic simulator fills
the columns OULAD cannot provide.

## Mapping: OULAD -> CAREERMIND

| OULAD table | CAREERMIND use | Collection |
|---|---|---|
| `studentInfo` | student profiles (programme, demographics) | `profiles` |
| `studentVle` | behavioural events (resource clicks w/ timestamps -> SCI, DFET signals) | `events` / `sessions` |
| `studentAssessment` | graded outcomes for Eq. 2 weight calibration | `profiles.academic_records` |
| `vle` | resource metadata (type -> LRDS thresholds) | `courses.resources` |
| `assessments` | assessment metadata | `courses.quizzes` |

## Gaps OULAD cannot fill (covered by `data/simulator/`)

* task start/completion granularity -> TCR
* quiz item-level re-attempt data -> QAP
* skill-assessment scores (RL state, ensemble features)
* career outcomes (ensemble labels) and career preferences

## Usage

```bash
python data/oulad/download.py --out data/oulad/raw/
```
