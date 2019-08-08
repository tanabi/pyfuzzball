#
# Tests for the MCP class
#
# Note that these are functional tests, because doing mocks is kind of
# a waste of time.
#
# Uses these environment variables:
#
# MUCK_HOST, MUCK_PORT, MUCK_SECURE_HOST, MUCK_SECURE_PORT
#
# We use Hope Island MUCK as a reasonable default.
#

import pytest
import os
import time

from pyfuzzball.mcp import MCP

@pytest.fixture(scope="session")
def fb():
    """Test a connection to a MUCK server."""
    
    return MCP(os.getenv('MUCK_HOST', 'hopeisland.net'),
               os.getenv('MUCK_PORT', '1024'),
               False
    )

@pytest.fixture(scope="session")
def fb_secure():
    return MCP(os.getenv('MUCK_SECURE_HOST', 'hopeisland.net'),
               os.getenv('MUCK_SECURE_PORT', '2048'),
               True, True
    )

@pytest.mark.dependency()
def test_connections(fb, fb_secure):
    """The fixtures should pass, and also we should have catalogs."""
    assert len(fb.catalog)
    assert len(fb_secure.catalog)

    # mcp-negotiate should probably be in the catalog assuming a non-broken
    # MUCK.
    assert 'mcp-negotiate' in fb.catalog
    assert 'mcp-negotiate' in fb_secure.catalog


@pytest.mark.dependency(depends=['test_connections'])
def test_version_compare(fb, fb_secure):
    """Test the version compare method.  Only need to test this unsecure."""

    assert fb.version_compare("2.0", "1.0") == 1
    assert fb.version_compare("1.0", "2.0") == -1
    assert fb.version_compare("1.0", "1.0") == 0
    assert fb.version_compare("2.2", "2.1") == 1
    assert fb.version_compare("2.1", "2.2") == -1
    assert fb.version_compare("2.1", "2.1") == 0


@pytest.mark.dependency(depends=['test_connections'])
def test_escape(fb, fb_secure):
    """Tests the escape call.  only need to test this unsecure."""

    assert fb.escape('This has "quotes"') == 'This has \\"quotes\\"'
    assert fb.escape('This has a backslash \\') == 'This has a backslash \\\\'
    assert fb.escape('This has \\"both\\"') == 'This has \\\\\\"both\\\\\\"'

@pytest.mark.dependency(depends=['test_connections'])
def test_unescape(fb, fb_secure):
    """Tests the unescape call.  only need to test this unsecure."""

    assert fb.unescape('This has \\"quotes\\"') == 'This has "quotes"'
    assert fb.unescape('This has a backslash \\\\') == 'This has a backslash \\'
    assert fb.unescape('This has \\\\\\"both\\\\\\"') == 'This has \\"both\\"'


@pytest.mark.dependency(depends=['test_connections'])
def test_call_and_process(fb, fb_secure):
    """These are really hard to de-couple, so this will do a call then
    process the result.
    """

    fb.call("org-fuzzball-help", "request", {"topic": "dbref", "type": "man"})

    # The first call to process is usually blank for some reason
    x = 0

    while x < 5:
        result = fb.process()

        if len(result[0]) or len(result[1]):
            break

        time.sleep(1)
        x += 1

    assert x < 5

    # See if we have proper results.
    assert 'org-fuzzball-help' in result[0]

    assert result[0]['org-fuzzball-help'][0]['message'] == 'entry'
    assert 'text' in result[0]['org-fuzzball-help'][0]['parameters']
    assert len(result[0]['org-fuzzball-help'][0]['parameters']['text']) == 3
