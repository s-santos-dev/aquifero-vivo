"""CLI para gerar datasets operacionais sintéticos do Aquífero Vivo."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.simulation import Scenario, SimulationConfig, generate_dataset, write_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera CSVs explicitamente classificados como SIMULATED."
    )
    parser.add_argument("--scenario", choices=[item.value for item in Scenario], default="NORMAL")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--wells", type=int, default=80)
    parser.add_argument("--sectors", type=int, default=20)
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2024, 1, 1))
    parser.add_argument(
        "--output",
        type=Path,
        help="Destino dentro de data/simulated (padrão: subdiretório do cenário).",
    )
    return parser.parse_args()


def _safe_output_path(requested: Path | None, scenario: Scenario) -> Path:
    simulated_root = (ROOT / "data" / "simulated").resolve()
    target = (requested or simulated_root / scenario.value.lower()).resolve()
    if target != simulated_root and simulated_root not in target.parents:
        raise ValueError(f"o destino deve permanecer dentro de {simulated_root}")
    return target


def main() -> None:
    args = parse_args()
    scenario = Scenario(args.scenario)
    output = _safe_output_path(args.output, scenario)
    config = SimulationConfig(
        scenario=scenario,
        seed=args.seed,
        well_count=args.wells,
        sector_count=args.sectors,
        days=args.days,
        start_date=args.start_date,
    )
    from app.simulation.validate import validate_dataset
    dataset = validate_dataset(generate_dataset(config))
    write_dataset(dataset, output)
    print(f"Dataset {scenario.value} SIMULATED gerado em {output}")
    print(dataset.counts)


if __name__ == "__main__":
    main()
