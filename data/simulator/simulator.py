#!/usr/bin/env python
"""Synthetic student-trajectory simulator (Phase 1).

Generates realistic behavioural logs, grades, skill assessments, and career
outcomes. Doubles as the DQN pre-training environment dynamics (paper Sec. V-C:
"pre-trained on simulated student trajectories before online deployment").

Design:
  * Each synthetic student has latent parameters:
      - ability        ~ drives grades, task completion (TCR), quiz correctness
      - motivation     ~ drives session regularity (SCI), quiz re-attempts (QAP),
                         resource depth (LRDS)
      - focus_tendency ~ drives distraction-free engagement (DFET)
      - domain_affinity ~ vector over career categories -> eventual career outcome
  * Per-session raw behavioural aggregates are sampled from distributions
    conditioned on the latents, so sub-metrics genuinely correlate with
    outcomes (enabling Eq. 2 calibration in Phase 2).
  * Sampling scales are lightly calibrated to OULAD marginals when the raw
    tables are available (mean daily clicks, mean assessment score).

This module produces RAW aggregates only — sub-metric computation (TCR, SCI,
DFET, QAP, LRDS) is Phase 2 (`careermind_ml.fes.submetrics`).
"""
import json
import pathlib
from datetime import datetime, timedelta

import numpy as np

SEED_PATH = pathlib.Path(__file__).resolve().parent.parent / "knowledge_graph" / "careers_seed.json"

RESOURCE_TYPES = ("video", "article", "exercise", "interactive")
CAREER_CATEGORIES = ("software", "data", "infrastructure", "security", "hardware", "management")

DEFAULT_CONFIG = {
    "sessions_per_student": 12,
    "base_login_minute": 9 * 60,      # 09:00
    "grade_mean_base": 35.0,          # grade = base + slope * ability + noise
    "grade_mean_slope": 55.0,
    "grade_sd": 8.0,
    "assessment_sd": 8.0,
    "oulad_calibration": None,        # dict of scale factors from OULAD, if available
}


class StudentSimulator:
    """Latent-parameter student generator + trajectory simulation."""

    def __init__(self, config: dict | None = None, seed: int | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.seed = int(seed) if seed is not None else 0
        self.rng = np.random.default_rng(seed)
        self._career_by_category, self._careers = self._load_careers()

    # ------------------------------------------------------------------ setup

    def _load_careers(self) -> tuple[dict, list]:
        """(category -> [career_id, ...], full career dicts) from the
        knowledge-graph seed (in sync with what the recommender will use)."""
        mapping = {cat: [] for cat in CAREER_CATEGORIES}
        careers = []
        try:
            with open(SEED_PATH) as fh:
                seed_data = json.load(fh)
            careers = seed_data["careers"]
            for career in careers:
                mapping.setdefault(career["category"], []).append(career["id"])
        except (OSError, KeyError):
            pass  # fall back to empty mapping; outcomes use category labels only
        return mapping, careers

    @staticmethod
    def calibrate_from_oulad(raw_dir: str | pathlib.Path) -> dict:
        """Light calibration to OULAD marginals: mean daily clicks per student
        and mean assessment score. Returns scale factors used by the simulator
        (interaction_scale, grade_offset). Best-effort: returns neutral defaults
        if the raw tables are absent."""
        raw_dir = pathlib.Path(raw_dir)
        interaction_scale, grade_offset = 1.0, 0.0
        try:
            clicks_per_day = {}
            with open(raw_dir / "studentVle.csv", newline="") as fh:
                import csv as _csv

                seen = 0
                for row in _csv.DictReader(fh):
                    key = (row["id_student"], row["date"])
                    clicks_per_day[key] = clicks_per_day.get(key, 0) + int(row["sum_click"])
                    seen += 1
                    if seen >= 200_000:  # sample the head only
                        break
            if clicks_per_day:
                oulad_mean = float(np.mean(list(clicks_per_day.values())))
                interaction_scale = max(0.5, min(3.0, oulad_mean / 60.0))
            scores = []
            with open(raw_dir / "studentAssessment.csv", newline="") as fh:
                import csv as _csv

                for row in _csv.DictReader(fh):
                    if row["score"] not in ("", None):
                        scores.append(float(row["score"]))
            if scores:
                grade_offset = float(np.mean(scores)) - 70.0  # our base grade mean is ~70
        except OSError:
            pass
        return {"interaction_scale": interaction_scale, "grade_offset": grade_offset}

    # -------------------------------------------------------------- students

    @staticmethod
    def _clip(x, lo=0.05, hi=0.98):
        return float(np.clip(x, lo, hi))

    def generate_students(self, n: int) -> list[dict]:
        """Sample n latent-parameter student profiles."""
        students = []
        for i in range(n):
            affinity = self.rng.dirichlet(np.ones(len(CAREER_CATEGORIES)))
            student = {
                "student_id": f"sim_{i + 1:04d}",
                "ability": self._clip(self.rng.normal(0.65, 0.15)),
                "motivation": self._clip(self.rng.normal(0.60, 0.20)),
                "focus_tendency": self._clip(self.rng.normal(0.55, 0.20)),
                "domain_affinity": {cat: float(a) for cat, a in zip(CAREER_CATEGORIES, affinity)},
            }
            students.append(student)
        return students

    # -------------------------------------------------------------- sessions

    def generate_sessions(self, student: dict, n_sessions: int | None = None) -> list[dict]:
        """Generate behavioural sessions (raw aggregates) conditioned on the
        student's latents. One `assessment_score` outcome is aligned to each
        session for Eq. 2 (sub-metric, outcome) pairing."""
        n_sessions = n_sessions or self.config["sessions_per_student"]
        ability = student["ability"]
        motivation = student["motivation"]
        focus = student["focus_tendency"]
        cal = self.config.get("oulad_calibration") or {}
        interaction_scale = cal.get("interaction_scale", 1.0)

        base_login = self.rng.integers(7 * 60, 22 * 60)
        day = datetime(2025, 3, 3)
        gap_shape = 1.0 + 2.5 * motivation  # higher motivation -> shorter gaps
        sessions = []
        for idx in range(n_sessions):
            day += timedelta(days=int(self.rng.gamma(gap_shape, 1.2)) + 1)
            login_minute = int(
                np.clip(
                    self.rng.normal(base_login, 45 * (1.05 - motivation)),
                    6 * 60,
                    23 * 60,
                )
            )
            duration = float(self.rng.lognormal(mean=np.log(25 + 40 * motivation), sigma=0.35))

            tasks_started = int(self.rng.poisson(1 + 2 * ability))
            tasks_completed = int(self.rng.binomial(tasks_started, 0.35 + 0.55 * ability))

            n_visits = int(self.rng.poisson(2 + 4 * focus))
            resource_visits = []
            for _ in range(n_visits):
                rtype = RESOURCE_TYPES[self.rng.integers(0, len(RESOURCE_TYPES))]
                dwell_mean = {"video": 420, "article": 240, "exercise": 300, "interactive": 260}[rtype]
                dwell = float(self.rng.exponential(dwell_mean * (0.6 + 0.8 * motivation)))
                idle_gap = float(self.rng.exponential(90 * (1.3 - focus)))
                resource_visits.append(
                    {
                        "type": rtype,
                        "dwell_seconds": dwell,
                        "idle_gap_seconds": idle_gap,
                        "rapid_switch": bool(self.rng.random() < 0.45 * (1 - focus)),
                    }
                )

            quiz_items = int(self.rng.poisson(2 + 3 * motivation))
            quiz_correct = int(self.rng.binomial(quiz_items, 0.35 + 0.55 * ability))
            quiz_incorrect = quiz_items - quiz_correct
            quiz_reattempts = int(self.rng.binomial(quiz_incorrect, 0.25 + 0.6 * motivation))

            # OULAD calibrates click MAGNITUDE (daily VLE clicks); the paper's
            # EngagementSignal needs live-platform action DENSITY (>= 3/min),
            # so focus contributes an extra per-minute interaction layer that
            # the daily totals do not capture.
            interaction_rate = (1.5 + 3.0 * focus) * interaction_scale + 2.0 * focus
            interactions = int(self.rng.poisson(duration * interaction_rate))

            assessment_score = float(
                np.clip(
                    self.rng.normal(
                        self.config["grade_mean_base"] + self.config["grade_mean_slope"] * ability,
                        self.config["assessment_sd"],
                    ),
                    0,
                    100,
                )
            )

            sessions.append(
                {
                    "student": student["student_id"],
                    "session_index": idx,
                    "date": day.date().isoformat(),
                    "login_minute_of_day": login_minute,
                    "duration_minutes": duration,
                    "tasks_started": tasks_started,
                    "tasks_completed": tasks_completed,
                    "resource_visits": resource_visits,
                    "quiz_items": quiz_items,
                    "quiz_items_correct": quiz_correct,
                    "quiz_reattempts": quiz_reattempts,
                    "interaction_count": interactions,
                    "assessment_score": assessment_score,
                }
            )
        return sessions

    # -------------------------------------------------------------- outcomes

    def generate_outcomes(self, student: dict, sessions: list[dict]) -> dict:
        """Generate graded outcomes (5 key subject grades), skill-assessment
        scores, and the eventual career-outcome label."""
        ability = student["ability"]
        grade_offset = (self.config.get("oulad_calibration") or {}).get("grade_offset", 0.0)
        grades = {}
        for subject in ("CS201", "CS230", "CS320", "ST210", "CS350"):
            grades[subject] = float(
                np.clip(
                    self.rng.normal(
                        self.config["grade_mean_base"] + self.config["grade_mean_slope"] * ability
                        + grade_offset,
                        self.config["grade_sd"],
                    ),
                    0,
                    100,
                )
            )

        # skills: correlated with ability and the student's domain affinity
        skill_scores = {}
        skills_by_category = {}
        skill_categories: dict = {}
        try:
            with open(SEED_PATH) as fh:
                for career in json.load(fh)["careers"]:
                    for prereq in career["prerequisites"]:
                        skills_by_category.setdefault(career["category"], set()).add(prereq["skill"])
                        skill_categories.setdefault(prereq["skill"], []).append(career["category"])
        except OSError:
            skills_by_category = {}
            skill_categories = {}
        affinity = np.array([student["domain_affinity"][c] for c in CAREER_CATEGORIES])
        affinity = affinity / affinity.sum()
        chosen_categories = self.rng.choice(len(CAREER_CATEGORIES), size=5, p=affinity)
        for cat_idx in chosen_categories:
            cat = CAREER_CATEGORIES[cat_idx]
            pool = sorted(skills_by_category.get(cat, []))
            if not pool:
                continue
            skill = pool[self.rng.integers(0, len(pool))]
            if skill in skill_scores:
                continue
            related = student["domain_affinity"].get(cat, 0.2)
            skill_scores[skill] = float(
                np.clip(self.rng.normal(25 + 60 * (0.65 * ability + 0.35 * related), 10), 0, 100)
            )

        # Assess every remaining KG skill too: a sparse profile would make the
        # prerequisite gate conflate "never assessed" with "below minimum".
        # Drawn from a per-student side stream so the main RNG sequence
        # (sessions, interactions, grades, career label) stays unchanged.
        seq = str(student.get("student_id") or "").rsplit("_", 1)[-1]
        fill_rng = np.random.default_rng([self.seed, int(seq) if seq.isdigit() else 0])
        for skill in sorted(skill_categories):
            if skill in skill_scores:
                continue
            cats = skill_categories[skill]
            related = float(np.mean([student["domain_affinity"].get(c, 0.2) for c in cats]))
            skill_scores[skill] = float(
                np.clip(fill_rng.normal(25 + 60 * (0.65 * ability + 0.35 * related), 10), 0, 100)
            )

        # career label: highest-affinity category; pick a concrete pathway in it
        career_category = max(student["domain_affinity"], key=student["domain_affinity"].get)
        candidates = self._career_by_category.get(career_category, [])
        career_pathway_id = (
            candidates[self.rng.integers(0, len(candidates))] if candidates else None
        )

        return {
            "grades": grades,
            "skill_scores": skill_scores,
            "career_category": career_category,
            "career_pathway_id": career_pathway_id,
        }

    # ----------------------------------------------------------- interactions

    def generate_interactions(self, student: dict, sessions: list[dict]) -> list[dict]:
        """Implicit-feedback interactions per session (Phase 4: CF/FM training data).

        Each session contributes one primary pathway engagement sampled from
        the student's domain affinity, sometimes a course from that pathway's
        typical courses, and occasionally an exploratory second pathway.
        Engagement WEIGHT (the session's FES) is joined from fes_history at
        model-build time — the interaction itself stores only the session key.
        """
        affinity = np.array([student["domain_affinity"][c] for c in CAREER_CATEGORIES])
        affinity = affinity / affinity.sum()
        typical_courses = {c["id"]: c.get("typical_courses", []) for c in self._careers}

        interactions = []
        for session in sessions:
            session_key = f"{student['student_id']}:{session['session_index']}"
            engaged = set()

            def _sample_pathway() -> str | None:
                cat_idx = self.rng.choice(len(CAREER_CATEGORIES), p=affinity)
                candidates = self._career_by_category.get(CAREER_CATEGORIES[cat_idx]) or []
                if not candidates:
                    return None
                return candidates[self.rng.integers(0, len(candidates))]

            pathway = _sample_pathway()
            if pathway is not None:
                engaged.add(("pathway", pathway))
                if self.rng.random() < 0.6 and typical_courses.get(pathway):
                    course = typical_courses[pathway][self.rng.integers(0, len(typical_courses[pathway]))]
                    engaged.add(("course", course))

            if self.rng.random() < 0.25:  # exploratory second pathway
                second = _sample_pathway()
                if second:
                    engaged.add(("pathway", second))

            for item_type, item_id in sorted(engaged):
                interactions.append(
                    {
                        "student": student["student_id"],
                        "item_type": item_type,
                        "item_id": item_id,
                        "session": session_key,
                        "date": session["date"],
                    }
                )
        return interactions

    # --------------------------------------------------------------- events

    @staticmethod
    def explode_events(session: dict) -> list[dict]:
        """Expand one session's raw aggregates into individual behavioural
        events (for the `events` collection). Timestamps are nominal."""
        base = datetime.fromisoformat(session["date"]).replace(
            hour=session["login_minute_of_day"] // 60,
            minute=session["login_minute_of_day"] % 60,
        )
        events = [{"type": "session_start", "timestamp": base.isoformat()}]
        t = base
        for visit in session["resource_visits"]:
            events.append({"type": "resource_open", "resource_type": visit["type"], "timestamp": t.isoformat()})
            t += timedelta(seconds=visit["dwell_seconds"])
            events.append({"type": "resource_close", "resource_type": visit["type"], "timestamp": t.isoformat()})
        for i in range(session["tasks_started"]):
            events.append({"type": "task_start", "timestamp": t.isoformat()})
        for i in range(session["tasks_completed"]):
            events.append({"type": "task_complete", "timestamp": t.isoformat()})
        if session["quiz_items"]:
            events.append({"type": "quiz_attempt", "metadata": {"items": session["quiz_items"]}, "timestamp": t.isoformat()})
        events.append({"type": "session_end", "timestamp": t.isoformat()})
        for e in events:
            e["student"] = session["student"]
            e["session_index"] = session["session_index"]
        return events
