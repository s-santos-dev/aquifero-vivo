"""python -m app.ingestion.rimas.cli --help"""
import argparse
import json
from pathlib import Path
from app.database import SessionLocal
from .client import Client
from .extract import extract, from_batch
from .transform import transform
from .load import load


def main():
    p = argparse.ArgumentParser(description="Piloto RIMAS no Piauí: CSV oficial, até 366 dias, sem consolidação")
    p.add_argument("--station")
    p.add_argument("--from", dest="start")
    p.add_argument("--to", dest="end")
    p.add_argument("--file", help="CSV oficial: verifica cadastro online e preserva cópia bruta")
    p.add_argument("--batch", help="Reprocessa lote bruto preservado, sem acesso à rede")
    p.add_argument("--raw-dir", default="/data/raw/rimas")
    p.add_argument("--processed-dir", default="/data/processed/rimas")
    p.add_argument("--load", action="store_true", help="Escrita transacional; padrão somente validação")
    args = p.parse_args()
    if args.batch:
        if any((args.station, args.start, args.end, args.file)): p.error("--batch não aceita seleção/arquivo")
        content, meta = from_batch(args.batch)
    else:
        if not all((args.station, args.start, args.end)): p.error("Informe --station, --from e --to")
        content, meta = extract(Client(), args.raw_dir, station=args.station, start=args.start, end=args.end, file=args.file)
    well, records, report = transform(content, meta)
    blocked = args.load and bool(report["rejected"])
    if args.load and not blocked:
        # Fail closed: rejected rows need explicit review before any live write.
        with SessionLocal.begin() as session: report["load"] = load(session, well, records)
    if blocked: report["load_blocked"] = "Lote com rejeições; revise antes de qualquer carga"
    folder = Path(args.processed_dir); folder.mkdir(parents=True, exist_ok=True)
    path = folder / (meta["batch"] + ("-load" if args.load else "-validate") + ".json")
    # Reports are separate from immutable raw files; each execution gets a new report.
    from uuid import uuid4
    path = path.with_name(path.stem + "-" + str(uuid4())[:8] + ".json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(report=report, report_file=str(path)), ensure_ascii=False, indent=2))
    if blocked: raise SystemExit(2)


if __name__ == "__main__": main()
