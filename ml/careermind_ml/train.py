"""CAREERMIND Part B training CLI.

Usage:
    python -m careermind_ml.train --module fes --config ml/configs/fes.yaml
    python -m careermind_ml.train --module fm --config ml/configs/fm.yaml
    python -m careermind_ml.train --module dqn --config ml/configs/dqn.yaml
    python -m careermind_ml.train --module ensemble --config ml/configs/ensemble.yaml
"""
import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="CAREERMIND model training (Part B)")
    parser.add_argument("--module", required=True, choices=["fes", "fm", "dqn", "ensemble"])
    parser.add_argument("--config", default=None, help="Path to YAML config (see ml/configs/)")
    parser.add_argument("--data", default=None, help="Path to training data (CSV/JSON)")
    args = parser.parse_args()

    if args.module == "fes":
        from careermind_ml.fes.weights import calibrate_student_weights  # noqa: F401
        print("Phase 2: FES weight calibration not implemented yet")
        return 1
    if args.module == "fm":
        from careermind_ml.recommender.fm import train_fm  # noqa: F401
        print("Phase 4: FM training not implemented yet")
        return 1
    if args.module == "dqn":
        from careermind_ml.rl.train import train_dqn  # noqa: F401
        print("Phase 6: DQN pre-training not implemented yet")
        return 1
    if args.module == "ensemble":
        from careermind_ml.career_prediction.ensemble import train_ensemble  # noqa: F401
        print("Phase 5: ensemble training not implemented yet")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
