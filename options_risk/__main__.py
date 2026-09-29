import argparse
import json
from pathlib import Path
from .scenarios import analyse


def main():
    parser = argparse.ArgumentParser(description='Fixed-contract option risk scenarios')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; choose a new path')
    try:
        request = json.loads(args.input.read_text(), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f'Invalid number: {v}')))
        result = analyse(request)
        content = json.dumps(result, indent=2, allow_nan=False)
        with args.output.open('x') as handle:
            handle.write(content+'\n')
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
