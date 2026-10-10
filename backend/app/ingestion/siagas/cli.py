"""python -m app.ingestion.siagas.cli --municipality Teresina --limit 25"""
import argparse
import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.database import engine
from .client import Client, SourceError
from .extract import extract, from_file, save
from .transform import transform
from .validate import selection
from .load import load
from .mappings import URL


def main():
    p = argparse.ArgumentParser(description="SIAGAS público; somente cadastros, sem reset ou medições")
    p.add_argument("--state", default="PI")
    p.add_argument("--municipality")
    p.add_argument("--bbox", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--page-size", type=int, default=100)
    p.add_argument("--input", type=Path)
    p.add_argument("--source-url", default=URL)
    p.add_argument("--raw-dir", type=Path, default=Path("../data/raw/siagas"))
    p.add_argument("--processed-dir", type=Path, default=Path("../data/processed/siagas"))
    p.add_argument("--load", action="store_true", help="Gravar transação validada; padrão apenas extrai/valida")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    chosen = dict(state=args.state, municipality=args.municipality, bbox=args.bbox, limit=args.limit)
    try:
        selection(**chosen)
        if args.input:
            envelope = from_file(args.input, source_url=args.source_url, **chosen)
            raw_copy = args.raw_dir / envelope["batch"] / "extraction.json"
            if not raw_copy.exists():
                save(raw_copy, envelope)
        else:
            envelope = extract(Client(), args.raw_dir, **chosen, page_size=args.page_size)
        records, report = transform(envelope)
        save(args.processed_dir / (envelope["batch"] + "-wells.json"), [{**r, "id": str(r["id"])} for r in records])
        if args.load:
            with Session(engine) as session, session.begin():
                report.update(load(session, records))
        else:
            report.update(created=0, updated=0, dry_run=True)
        save(args.processed_dir / (envelope["batch"] + "-report.json"), report)
        print(json.dumps(report, ensure_ascii=False))
    except SQLAlchemyError:
        p.exit(1, "Falha de banco; transação revertida. Verifique conexão/migrations e repita o lote validado.\n")
    except (SourceError, ValueError, OSError) as exc:
        p.exit(1, f"Importação interrompida: {exc}\nUse --input para arquivo oficial obtido legalmente.\n")


if __name__ == "__main__":
    main()
