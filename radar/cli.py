import argparse
import json


def main():
    p = argparse.ArgumentParser(description="ResearchRadar reproducible pipeline")
    sub = p.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--output", default="data/corpus.json")
    ingest.add_argument("--start", type=int, default=2017)
    ingest.add_argument("--end", type=int, default=2024)
    ingest.add_argument("--per-year", type=int, default=600)
    ingest.add_argument("--seed", type=int, default=42)
    fit = sub.add_parser("train")
    fit.add_argument("--corpus", default="data/corpus.json")
    fit.add_argument("--output", default="dist")
    fit.add_argument("--observed-through", type=int, default=2025)
    fit.add_argument("--train-end", type=int, default=2019)
    fit.add_argument("--calibration-year", type=int, default=2021)
    fit.add_argument("--test-start", type=int, default=2023)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    if args.command == "ingest":
        from radar.ingest import collect
        collect(args.output, range(args.start, args.end + 1), args.per_year, args.seed)
    elif args.command == "train":
        from radar.model import train
        report = train(args.corpus, args.output, args.observed_through, args.train_end, args.calibration_year, args.test_start)
        print(json.dumps({k: report[k] for k in ["train_n", "calibration_n", "test_n", "full_model", "metadata_baseline"]}, indent=2))
    else:
        import uvicorn
        uvicorn.run("radar.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
