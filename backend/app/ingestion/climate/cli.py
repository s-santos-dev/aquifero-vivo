import argparse
import json
from pathlib import Path
from uuid import uuid4
from app.database import SessionLocal
from .client import Client
from .extract import extract, from_batch
from .transform import transform
from .load import load


def main():
    p = argparse.ArgumentParser(description="INMET: arquivo anual oficial, observações horárias e dias UTC completos")
    p.add_argument("--station")
    p.add_argument("--from", dest="start")
    p.add_argument("--to", dest="end")
    p.add_argument("--file", help="ZIP oficial obtido pelo download normal do portal")
    p.add_argument("--batch", help="Reprocessar lote offline com checksums")
    p.add_argument("--raw-dir", default="/data/raw/climate")
    p.add_argument("--processed-dir", default="/data/processed/climate")
    p.add_argument("--load", action="store_true")
    args = p.parse_args()
    if args.batch:
        if any((args.station,args.start,args.end,args.file)):
            p.error("--batch não aceita nova seleção")
        content,meta = from_batch(args.batch)
    else:
        if not all((args.station,args.start,args.end)):
            p.error("Informe estação, início e fim")
        content,meta = extract(Client(),args.raw_dir,station=args.station,start=args.start,end=args.end,file=args.file)
    _,_,report = transform(content,meta)
    blocked = bool(report["rejected"] or not report["observed"])
    if args.load and not blocked:
        with SessionLocal.begin() as session:
            report["load"] = load(session,content,meta)
    if args.load and blocked:
        report["load_blocked"] = "Rejeições ou ausência de observações válidas"
    path = Path(args.processed_dir) / (meta["batch"] + "-" + uuid4().hex[:8] + ".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(dict(report_file=str(path),**{k:v for k,v in report.items() if k not in ("daily",)}),ensure_ascii=False,indent=2))
    if blocked:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
