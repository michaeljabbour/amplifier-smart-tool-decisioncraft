"""Attribution exceptions cannot hide new or differently scoped contacts."""
import hashlib
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('generic_check', Path(__file__).parents[1] / 'scripts/check-generic.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_existing_metadata_fingerprint_does_not_exempt_new_commit_or_source():
    contact = 'person' + '@' + 'private.invalid'
    allowed = {('old', 'author_email', hashlib.sha256(contact.encode()).hexdigest())}
    assert module.metadata_email('old', 'author_email', contact, allowed)[1]
    assert not module.metadata_email('new', 'author_email', contact, allowed)[1]
    assert not module.metadata_email('old', 'committer_email', contact, allowed)[1]
    assert module.scan(contact, 'source', [])
    assert module.scan(contact, 'commit message', [])
