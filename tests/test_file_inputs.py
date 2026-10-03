import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from options_risk.file_inputs import portfolio_input, quote_input, load_download
from options_risk.scenarios import analyse


class DownloadReplayTest(unittest.TestCase):
    def test_discriminated_formats_and_ambiguous_input(self):
        request = json.loads(Path('examples/portfolio.json').read_text())
        for payload, kind in [
            (request, 'portfolio_request'),
            ({'request': request, 'result': {}}, 'browser_portfolio_export'),
            ({'request': request, 'source_note': 'unverified'}, 'quote_derived_portfolio'),
        ]:
            self.assertEqual(portfolio_input(payload), (request, kind))
        for payload in [{'request': request}, {'request': request, 'rows': []},
                        {'request': request, 'result': {}, 'unknown': 1},
                        {'request': request, 'source_note': None}]:
            with self.assertRaises(ValueError):
                portfolio_input(payload)
        with self.assertRaises(ValueError):
            quote_input({'request': request, 'result': {}})

    def test_untrusted_json_is_rejected_before_unwrapping(self):
        for raw in ['{"request":{},"result":{"x":NaN}}',
                    '{"request":{},"result":{"x":1e999}}',
                    '{"request":{},"result":{},"request":{}}']:
            with self.assertRaises(ValueError):
                load_download(raw)

    def test_portfolio_cli_recomputes_both_download_types(self):
        request = json.loads(Path('examples/portfolio.json').read_text())
        expected = analyse(request)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, metadata in enumerate([{'result': {'market_value': 999999}},
                                               {'source_note': 'Unverified <script>text</script>'}]):
                source = root / f'input{index}.json'
                source.write_text(json.dumps({'request': request, **metadata}))
                before = source.read_bytes()
                output, html = root/f'out{index}.json', root/f'out{index}.html'
                run = subprocess.run([sys.executable, '-m', 'options_risk', str(source),
                    '--output', str(output), '--html', str(html)], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(json.loads(output.read_text()), expected)
                self.assertEqual(source.read_bytes(), before)
                self.assertIn(hashlib.sha256(before).hexdigest(), html.read_text())
                self.assertIn('Stored results and source notes', html.read_text())
                self.assertNotIn('<script>text</script>', html.read_text())

    def test_quote_output_replays_twice_ignoring_saved_results(self):
        request = json.loads(Path('examples/quotes.json').read_text())
        # Keep this an intake test, not a repeated tree convergence run.
        request['quotes'] = [q for q in request['quotes'] if q['style'] == 'european']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'quotes.json'
            source.write_text(json.dumps(request))
            first = None
            for index in range(3):
                before = source.read_bytes()
                output = root/str(index)
                run = subprocess.run([sys.executable, '-m', 'options_risk.quotes', str(source),
                    '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                result = json.loads((output/'result.json').read_text())
                if first is None:
                    first = copy.deepcopy(result)
                self.assertEqual(result['rows'], first['rows'])
                self.assertEqual(result['input_sha256'], hashlib.sha256(before).hexdigest())
                self.assertEqual(source.read_bytes(), before)
                result['rows'] = [{'status': 'fabricated'}]
                result['attention_count'] = 999
                source = root/f'tampered{index}.json'
                source.write_text(json.dumps(result))
