#
# Tests for the base class
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

from pyfuzzball.base import FuzzballBase

@pytest.fixture(scope="session")
def fb():
    """Test a connection to a MUCK server."""
    
    return FuzzballBase(os.getenv('MUCK_HOST', 'hopeisland.net'),
                        os.getenv('MUCK_PORT', '1024'),
                        False
    )

@pytest.fixture(scope="session")
def fb_secure():
    return FuzzballBase(os.getenv('MUCK_SECURE_HOST', 'hopeisland.net'),
                        os.getenv('MUCK_SECURE_PORT', '2048'),
                        True, True
    )
 
@pytest.mark.dependency()
def test_connections(fb, fb_secure):
    """If the fixtures passed, this worked!"""
    pass

@pytest.mark.dependency(depends=['test_connections'])
def test_read(fb, fb_secure):
    """Test to make sure we can read the input banner"""

    assert len(fb.read(5, True)) == 5
    assert len(fb_secure.read(5, True)) == 5

@pytest.mark.dependency(depends=['test_read'])
def test_readlines(fb, fb_secure):
    """Test our readline"""

    lines = []

    while True:
        line = fb.readline(-1)

        if line in (None, ""):
            break

        lines.append(line)

    assert len(lines)

    lines = []
    
    # Make sure there's data to read, sometimes this lags a moment.
    lines.append(fb_secure.readline(True))

    while True:
        line = fb_secure.readline()

        if line in (None, ""):
            break

        lines.append(line)

    assert len(lines)

@pytest.mark.dependency(depends=['test_readlines'])
def test_write(fb, fb_secure):
    """Now try to write"""

    fb.write("QUIT\r\n")
    fb_secure.write("QUIT\r\n")

    fb.close()
    fb_secure.close()
