"""Seed transacional, idempotente e restrito à origem deste simulador."""
import argparse
import json
from datetime import date
from pathlib import Path

from sqlalchemy import delete, func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import engine
from app.models import (
    Alert,
    GroundwaterMeasurement,
    OperationalMeasurement,
    RainfallMeasurement,
    RiskAssessment,
    Well,
    WellSector,
)
from app.simulation import Scenario, SimulationConfig, generate_dataset, write_dataset
from app.simulation.normalize import SOURCE, normalized_batches
from app.simulation.validate import validate_dataset


def seed_dataset(session: Session, dataset, *, reset=False):
    """Caller owns the transaction. A conflict with foreign provenance aborts it.

    ``reset`` removes obsolete simulator-only catalog rows when the configured
    well count is reduced. A well with any non-simulator reference is retained.
    Stable UUIDs upsert this simulator's records, independently of scenario/seed.
    """
    validate_dataset(dataset)
    session.execute(text("SELECT pg_advisory_xact_lock(71840261)"))
    if reset:
        for model in (GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement):
            session.execute(delete(model).where(model.source == SOURCE, model.data_classification == "SIMULATED"))
        desired_well_ids = [row["id"] for row in next(
            rows for model, rows in normalized_batches(dataset) if model is Well
        )]
        obsolete_simulated_wells = (
            Well.source == SOURCE,
            Well.data_classification == "SIMULATED",
            Well.id.not_in(desired_well_ids),
        )
        session.execute(
            delete(WellSector).where(
                WellSector.source == SOURCE,
                WellSector.data_classification == "SIMULATED",
                WellSector.well_id.not_in(desired_well_ids),
            )
        )
        # Any remaining child row belongs to another source or has no safe
        # provenance marker. Retaining the well avoids a cascade over it.
        session.execute(
            delete(Well).where(
                *obsolete_simulated_wells,
                ~GroundwaterMeasurement.__table__.select()
                .where(GroundwaterMeasurement.well_id == Well.id)
                .exists(),
                ~OperationalMeasurement.__table__.select()
                .where(OperationalMeasurement.well_id == Well.id)
                .exists(),
                ~WellSector.__table__.select().where(WellSector.well_id == Well.id).exists(),
                ~RiskAssessment.__table__.select().where(RiskAssessment.well_id == Well.id).exists(),
                ~Alert.__table__.select().where(Alert.well_id == Well.id).exists(),
            )
        )
    counts = {}
    for model, records in normalized_batches(dataset):
        for offset in range(0, len(records), 1000):
            batch = records[offset:offset + 1000]
            # Geometry serialization uses PostGIS, in the same transaction as all writes.
            for row in batch:
                for field in ("location", "boundary"):
                    if field in row:
                        row[field] = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(row[field])), 4326)
            spatial = any(field in batch[0] for field in ("location", "boundary"))
            statement = insert(model.__table__)
            if spatial:
                statement = statement.values(batch)
            statement = statement.on_conflict_do_update(
                index_elements=[model.id],
                set_={**{key: getattr(statement.excluded, key) for key in batch[0] if key != "id"}, "updated_at": func.now()},
                where=(model.source == SOURCE) & (model.data_classification == "SIMULATED"),
            ).returning(model.id)
            changed = len(session.execute(statement, None if spatial else batch).all())
            if changed != len(batch):
                raise ValueError("Colisão com registro não pertencente ao simulador; operação cancelada")
        counts[model.__tablename__] = len(records)
    return counts


def main():
    parser = argparse.ArgumentParser(description="Gera, valida e popula os contratos normais da aplicação com dados SIMULATED.")
    parser.add_argument("--scenario", choices=[s.value for s in Scenario])
    parser.add_argument("--seed", type=int)
    parser.add_argument("--wells", type=int)
    parser.add_argument("--sectors", type=int)
    parser.add_argument("--days", type=int)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--reset", action="store_true", help="Remove somente medições SIMULATED deste gerador; preserva cadastros e outras origens.")
    parser.add_argument("--dry-run", action="store_true", help="Gera e valida sem acessar o banco.")
    parser.add_argument("--export", action="store_true", help="Exporta CSVs opcionais em data/simulated/<cenário>.")
    args = parser.parse_args()
    config = SimulationConfig.from_env(scenario=args.scenario, seed=args.seed, well_count=args.wells,
        sector_count=args.sectors, days=args.days, start_date=args.start_date)
    print(f"Generating {config.scenario.value}: {config.well_count} wells × {config.days} days...", flush=True)
    dataset = validate_dataset(generate_dataset(config))
    print("Dataset validated. Normalizing shared schemas...", flush=True)
    if args.export:
        root = Path(__file__).resolve().parents[3] / "data" / "simulated"
        write_dataset(dataset, root / config.scenario.value.lower())
    if args.dry_run:
        # Validate normalization too, even without a database.
        counts = {model.__tablename__: len(rows) for model, rows in normalized_batches(dataset)}
    else:
        with Session(engine) as session, session.begin():
            counts = seed_dataset(session, dataset, reset=args.reset)
    print("Simulation validated (dry run)." if args.dry_run else "Simulation completed.")
    print(f"Scenario: {config.scenario.value}\nSeed: {config.seed}\nWells: {config.well_count}\nSectors: {config.sector_count}\nDays: {config.days}")
    print(json.dumps(counts, indent=2))
    print("Data classification: SIMULATED\nIs synthetic: true\nRows are upserted, never presented as real observations.")


if __name__ == "__main__":
    main()
