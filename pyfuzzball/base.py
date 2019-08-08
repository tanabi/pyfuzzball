#
# base.py
#
# Provides base interface for doing I/O with the MUCK.  Its basically the
# primitives used by the higher level classes.
#
# HopeIslandCoder - 01/17/2019 - Public Domain

import socket
import ssl

from io import StringIO
from selectors import DefaultSelector, EVENT_READ


class FuzzballBase(object):
    def __init__(self, host, port, use_ssl=False, ignore_ssl_cert=False):
        """Set up the class, and do the initial connection.

        Args:
            host: (str) hostname
            port: (int) port
            use_ssl: (bool) use SSL or not
            ignore_ssl_errors: (bool) If we should ignore SSL certificate issues
        """

        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.ignore_ssl_cert = ignore_ssl_cert

        self.socket = None
        self.selector = DefaultSelector()

        # We'll use the buffer to capture partial lines, then the lines
        # object to transmute buffer into actionable lines.
        #
        # Kind of messy, but that's the world we live in.
        self.buffer = None  # Will be a StringIO
        self.lines = []

        self.connect()

    def connect(self):
        """Connect to the MUCK."""

        self.socket = socket.create_connection((self.host, self.port))

        if self.use_ssl:
            if self.ignore_ssl_cert:
                self.socket = ssl.wrap_socket(self.socket,
                                              cert_reqs=ssl.CERT_NONE)
            else:
                self.socket = ssl.wrap_socket(self.socket,
                                              cert_reqs=ssl.CERT_REQUIRED)

        self.selector.register(self.socket, EVENT_READ)

    def close(self):
        """Close the connection -- this does NOT send a QUIT or do any nice
        cleanup beyond cleaning up the socket.
        """

        # Be nice and actually shut down before closing.
        self.socket.shutdown(2)
        self.socket.close()

        self.socket = None

    def read(self, size=8194, timeout=0):
        """This will do a raw read of up to 'size' bytes.  It is recommended
        'size' be 8194 as that will be the typical max buffer size (8192) plus
        a couple extra bytes for a \r\n which should (usually) be the most
        you'd get from a MUCK at any one time.

        If timeout is 0 or more, we'll look before we will return an empty
        string rather than block.  None is returned if the connection is closed.

        This always returns strings, never python bytes objects.

        You can't mix this and readline -- readline does extensive buffering.

        Arguments:
            size: (int) Maximum number of bytes to read
            timeout: (int) -1 to block, or 0 - whatever to have a timeout

        Returns:
            Either a string of text, empty string, or None -- see description
        """

        if timeout >= 0:
            ev = self.selector.select(timeout)

            if not len(ev):
                return ""

        return self.socket.recv(size).decode("ascii")

    def readline(self, timeout=0):
        """Reads a line of text.

        If timeout is 0 or more, we will return an empty string
        rather than block.  None is returned if the connection is closed.

        This always returns strings, never python bytes objects.

        Arguments:
            block: (bool) To block or not to block, thas is the question.

        Returns:
            Either a string of text, empty string, or None -- see description
        """

        # If we've got lines, send 'em
        #
        # Sometimes this has blanks -- kick the blanks out.
        # I think this may be a bug in the buffer logic but it is a
        # little too painful to figure out why, so this seems to resolve
        # it.
        while len(self.lines):
            line = self.lines.pop(0)

            if line:
                return line

        # If we would block, let's go ahead and return.
        if timeout < 0:
            ev = self.selector.select(None)
        else:
            ev = self.selector.select(timeout)

        if not len(ev):
            return ""

        # We have data - do we have a partial line in the buffer?
        if self.buffer is None:
            self.buffer = StringIO()

        # Read as much data as we can into the buffer.
        while True:
            line = self.socket.recv(1024).decode('ascii')

            # Python will give an empty string if the connection is closed.
            # But select will keep saying there is data to read.  Thus making
            # an infinite loop.
            if line == "":
                return None

            self.buffer.write(line)

            ev = self.selector.select(0.1)

            if not len(ev):
                break

        # Now, the following could happen:
        #
        # 1. We have a tidy buffer of newline-delimited lines
        # 2. We have an incomplete line
        # 3. We have some lines and an incomplete.
        buffer_value = self.buffer.getvalue()
        buffer_lines = buffer_value.split("\r\n")
        self.buffer.close()

        # Is the last line an incomplete?  If so, jam it back into
        # the buffer.
        if buffer_value[-1:] != "\n":
            self.buffer = StringIO()
            self.buffer.write(buffer_lines.pop())
        else:
            self.buffer = None

        self.lines = buffer_lines

        # This will return the first element of lines, if set, or
        # check for more IO

        return self.readline(False)

    def write(self, s):
        """Sends a string to the MUCK.  This call will write the whole
        string, or raise an exception if it fails (usually due to MUCK
        disconnecting)

        Arguments:
            s: string text to write to the socket

        Returns:
            Nothing
        """

        self.socket.sendall(s.encode('ascii'))

    def login(self, user, password):
        """Logs in as a given user and password.

        Arguments:
            user: str user name
            password: str password

        Returns:
            boolean - True if login successful, false if not.
        """

        self.write("connect %s %s\r\n" % (user, password))

        # See if we logged in
        line = self.readline(-1)

        if "either that player does not exist" in line.lower():
            return False

        # Put the line back in for readline since this will probably
        # be the start of the motd
        self.lines.insert(0, line)

    def quit(self):
        """Does a proper 'nice' QUIT and closes the connection."""

        self.write("QUIT\r\n")
        self.close()
