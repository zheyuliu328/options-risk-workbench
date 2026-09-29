import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CLITest(unittest.TestCase):
    def test_real_example_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'result.json'
            command = [sys.executable, '-m', 'options_risk', 'examples/portfolio.json', '--output', str(output)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            original = output.read_bytes()
            result = json.loads(original)
            self.assertEqual(result['scenarios'][0]['pnl'], 0)
            self.assertEqual(len(result['positions']), 2)
            repeat = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(repeat.returncode, 0)
            self.assertEqual(output.read_bytes(), original)

    def test_rejects_non_json_numbers_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'input.json'
            output = Path(tmp)/'output.json'
            source.write_text('{"spot": NaN}')
            run = subprocess.run([sys.executable, '-m', 'options_risk', str(source), '--output', str(output)], capture_output=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertFalse(output.exists())
