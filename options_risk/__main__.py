import argparse
import json
import hashlib
from pathlib import Path
from .scenarios import analyse
from .report import render
from .file_inputs import DOWNLOAD_LIMIT, portfolio_input, load_download


def main():
    parser = argparse.ArgumentParser(description='Fixed-contract option risk scenarios')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--html', type=Path, help='Optional offline readable report')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; choose a new path')
    if args.html and (args.html.exists() or args.html.resolve() == args.output.resolve()):
        parser.error('HTML output must be a new, different path')
    try:
        raw = args.input.read_bytes()
        request, input_format = portfolio_input(load_download(raw))
        result = analyse(request)
        # Preserve the existing machine-readable result; provenance below is report-only.
        content = json.dumps(result, indent=2, allow_nan=False)
        if input_format != 'portfolio_request':
            result['assumptions'].append(DOWNLOAD_LIMIT)
        result['assumptions'].append('Input format: '+input_format+'; original input SHA-256: '+hashlib.sha256(raw).hexdigest())
        html = render(result, request) if args.html else None
        with args.output.open('x') as handle:
            handle.write(content+'\n')
        if args.html:
            with args.html.open('x') as handle:
                handle.write(html)
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
