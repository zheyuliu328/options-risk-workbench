"""Local CLI handoff for plain requests and the workbench's portfolio downloads."""
from .scenarios import fields


DOWNLOAD_LIMIT = (
    'Only the downloaded request was recomputed. Stored results and source notes '
    'were not used, authenticated or validated; the file hash identifies the original download.')


def portfolio_input(payload):
    """Return original inputs only; never use a saved calculation as an oracle."""
    if not isinstance(payload, dict) or 'request' not in payload:
        return payload, 'portfolio_request'
    fields(payload, ['request', 'result', 'source_note'], ['request'], 'browser export')
    if 'result' not in payload and 'source_note' not in payload:
        raise ValueError('browser export requires result or source_note')
    if not isinstance(payload['request'], dict) or ('result' in payload and not isinstance(payload['result'], dict)):
        raise ValueError('browser export request and result must be objects')
    if 'source_note' in payload and not isinstance(payload['source_note'], str):
        raise ValueError('browser export source_note must be text')
    return payload['request'], ('browser_portfolio_export' if 'result' in payload else 'quote_derived_portfolio')


def quote_input(payload):
    """Recognise quote reports, while refusing portfolio or ambiguous envelopes."""
    if not isinstance(payload, dict) or 'request' not in payload:
        return payload, 'quote_request'
    fields(payload, ['request', 'rows', 'attention_count', 'limits', 'input_sha256', 'input_format'],
           ['request', 'rows', 'attention_count', 'limits'], 'quote report')
    if (not isinstance(payload['request'], dict) or not isinstance(payload['rows'], list)
            or not isinstance(payload['limits'], list) or type(payload['attention_count']) is not int):
        raise ValueError('quote report requires request object, rows/limits lists and integer attention_count')
    for key in ('input_sha256', 'input_format'):
        if key in payload and not isinstance(payload[key], str):
            raise ValueError('quote report '+key+' must be text')
    return payload['request'], 'quote_report'


def load_download(raw):
    """Reject ambiguous JSON even in saved fields that will not be reused."""
    import json
    import math

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field: '+key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError('Invalid JSON number: '+value)

    def floating(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            invalid(value)
        return parsed

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid, parse_float=floating)
