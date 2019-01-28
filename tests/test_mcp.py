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

