"""Local CLI handoff for plain requests and the workbench's portfolio downloads."""
from .scenarios import fields


DOWNLOAD_LIMIT = (
    'Only the downloaded request was recomputed. Stored results and source notes '
    'were not used, authenticated or validated; the file hash identifies the original download.')


def portfolio_input(payload):
    """Return original inputs only; never use a saved calculation as an oracle."""
    if not isinstance(payload, dict) or 'request' not in payload:
        return payload, 'portfolio_request'
    fields(payload, ['request', 'result', 'source_note'], ['request', 'result'], 'browser export')
    if not isinstance(payload['request'], dict) or not isinstance(payload['result'], dict):
        raise ValueError('browser export request and result must be objects')
    if 'source_note' in payload and not isinstance(payload['source_note'], str):
        raise ValueError('browser export source_note must be text')
    return payload['request'], 'browser_portfolio_export'
