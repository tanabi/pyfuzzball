#
# mcp.py
#
# Provides an interface for doing MCP calls to the MUCK.
#
# HopeIslandCoder - 01/22/2019 - Public Domain

import random
import re
import string
import time

from io import StringIO
from pyfuzzball.base import FuzzballBase


class MCP(FuzzballBase):
    def __init__(self, host, port, use_ssl=False, ignore_ssl_cert=False):
        """This constructor takes the usual parameters and passes it to
        the base.  Then it handles the MCP negotiation.

        Args:
            host: (str) hostname
            port: (int) port
            use_ssl: (bool) use SSL or not
            ignore_ssl_errors: (bool) If we should ignore SSL certificate issues
        """

        super(MCP, self).__init__(host, port, use_ssl, ignore_ssl_cert)

        # Get MCP version from header line.
        #
        # It actually takes a couple seconds for the MUCK to load the
        # welcome screen properly, so wait til we get a full line out.
        mcp_proto = ""
        tries = 0

        while not mcp_proto and tries < 3:
            mcp_proto = self.readline(10)
            tries = tries + 1

        if tries >= 3:
            raise RuntimeError("No response from MUCK server.")

        res = re.match(r'#\$#mcp version: "([\d.]+)" to: "([\d.]+)"',
                       mcp_proto
        )

        if not res:
            raise RuntimeError("MCP header not found on MUCK login screen.")

        # We need these values to negotiate.  Make sure we support the
        # MCP version.
        #
        # TODO: Rather than echo back the server version numbers, this
        # library should support a version -- say, 2.1 -- and give a logical
        # answer with a check to make sure the server speaks the same version
        # we do.
        #
        # I am dubious this version will change anytime soon though.
        self.mcp_proto_from = res.group(1)
        self.mcp_proto_to = res.group(2)

        # Generate random auth string
        self.auth = self.generate_tag()

        # Clear buffer
        x = self.readline()

        while x:
            x = self.readline(0.1)

        # Our catalog of MCP events.
        self.catalog = {}

        # Make sure we only do this once per call.  The client
        # negotiation is the negotiate(...) call.
        self.client_negotiated = set()

        self._negotiate()

        # Now we're ready to go.

    def _negotiate(self):
        """This is a 'private' method that handles the MCP negotiation when
        first connecting to the server.  It is supposed to be called by
        the constructor only.
        """

        # Negotiate
        self.write(
            '#$#mcp authentication-key: "%s" version: "%s" to: "%s"\r\n'
            % (self.auth, self.mcp_proto_from, self.mcp_proto_to)
        )

        # Negotiation regex
        nego_re = re.compile(
            '^#\\$#mcp-negotiate-can %s package: "(.+)" min-version: \"(.+)\"'
            ' max-version: \"(.+)\"' % self.auth
        )

        # Get negotiate response
        # Timeout after 5 seconds.
        end = time.time() + 5

        while time.time() < end:
            line = self.readline(0.25)

            # We got the whole event list
            if line.startswith("#$#mcp-negotiate-end %s" % self.auth):
                break

            # For a valid MCP line, we want to add it to our
            # catalog of available methods.
            matches = nego_re.match(line)

            if matches:
                self.catalog[matches[1]] = (matches[2], matches[3])

        if time.time() >= end:
            raise RuntimeError("Timed out while getting event catalog.")

    def negotiate(self, packages):
        """This is a public call that handles the *second* MCP negotiation.
        The first MCP negotiation establishes the authentication key and
        the list of available server packages; this is handled by the
        constructor.

        The second MCP negotiation is the client telling the server
        which versions of the packages it desires.

        This step is technically optional; if you just use 'call' without
        negotiating first, it will auto-negotiate for you, however
        subsequent calls will fail because it will only negotiate for the
        one package you wish to use.

        So use this method if you wish to do calls to multiple different
        packages.

        Arguments:
            packages: list of strings

            The packages are provided with a list of strings that look like:

            packagename:min-version:max-version

            You can leave version off if you wish it to default to the
            versions supported by the server

            mcp-negotiate package is always added; you don't need to manually
            add that one.

        Returns:
            Nothing.  This will always succeed, or throw an exception.
        """

        # Have we already done this?
        if len(self.client_negotiated):
            raise RuntimeError("Can only negotiate once per session")

        # make our request
        request = StringIO()

        # Add MCP Negotiate package
        if "mcp-negotiate" in self.catalog:
            packages.append("mcp-negotiate")
            self.client_negotiated.add("mcp-negotiate")

        for package in packages:
            if ":" in package:
                package, min_version, max_version = package.rsplit(':', 2)

                if package not in self.catalog:
                    raise RuntimeError("Package %s not available on server" %
                                        package)
            else:
                if package not in self.catalog:
                     raise RuntimeError("Package %s not available on server" %
                                        package)

                min_version = self.catalog[package][0]
                max_version = self.catalog[package][1]

            self.client_negotiated.add(package)

            # Add it to our request
            request.write('#$#mcp-negotiate-can %s package: "%s" '
                          'min-version: "%s" max-version: "%s"\r\n' %
                          (self.auth, package, min_version, max_version))

        # Write end statement
        request.write("#$#mcp-negotiate-end %s\r\n" % self.auth)

        # Send it
        self.write(request.getvalue())

        # This should not produce any output from the server so no need
        # to read it.

    def generate_tag(self):
        """Generates a random tag, suitable for _data_tag or auth token.

        Returns:
            Some random string
        """
        return ''.join(random.choices(string.ascii_uppercase +
                                      string.digits, k=10))

    def escape(self, txt):
        """Does MCP escaping on " and backslash for a given text block, and
        returns the escaped text.

        Arguments:
            txt: str, the text to escape

        Returns:
            str, escaped text
        """

        return txt.replace("\\", "\\\\").replace('"', '\\"')

    def call(self, package, arguments={}, min_version=None, max_version=None):
        """This calls a given package.  If you have not yet run 'negotiate',
        this call will first negotiate for the use of the package with
        the provided min and max versions (or echo back the versions
        provided by the server if not provided).

        Please note that if you wish to do call's to multiple packages, you
        must use the negotiate call first and select the packages you want
        to use.

        Arguments is mapping of keys to string values.  You can map keys
        to lists of strings to do multi-line variables; the details of this
        are handled for you automatically.

        This will not return anything, but you can use the process()
        call to process server responses to get return values.

        Arguments:
            package: str indicating package name
            arguments: dict of strings mapping to strings, or lists of strings
            min_version: Optional minimum version; only used in auto-negotiate
            max_version: Optional maximum version; only used in auto-negotiate

        Returns:
            Nothing.
        """

        # Basic validation that the package is ready to be used with the
        # server.
        if not len(self.client_negotiated):
            if min_version and max_version:
                package_name = "%s:%s:%s" % (package, min_version, max_version)
            elif min_version or max_version:
                raise RuntimeError("You must provide both min_version and "
                                    "max_version, or neither.")
            else:
                package_name = package

            self.negotiate([package_name])
        elif package not in self.client_negotiated:
            raise RuntimeError("Package %s was not negotiated with the server."
                                % package)

        # Multi-line messages need data tags.
        need_data_tag = False

        buf = StringIO()

        buf.write('#$#%s %s' % (package, self.auth))

        for key, val in arguments.items():
            if isinstance(val, list):
                need_data_tag = True
                buf.write(' %s*: ""' % key)
            else:
                buf.write(' %s: "%s"' % key, self.escape(val))

        # Do we need data_tag ?
        if need_data_tag:
            data_tag = self.generate_tag()

            buf.write(' _data-tag: "%s"' % data_tag)

        buf.write('\r\n')

        # Do we have multiline stuff?
        if need_data_tag:
            for key, val in arguments.items():
                if not isinstance(val, list):
                    continue # Skip non-list items

                # For each list item, break it out nice.
                for line in val:
                    buf.write('#$#* %s %s: %s\r\n' % (data_tag, key, line))

                buf.write('#$#: %s\r\n' % data_tag)

        # Ship it
        self.write(buf.getvalue())

    def process(self, block=False):
        """This processes the output from the server and returns it in a
        consumable fashion.

        I have considered making a callback register where process can do
        callbacks based on the events sent from MCP.  I still may support
        that, however, it is overkill for the relatively simple stuff I
        wish to accomplish in the near term and I've already spent too much
        time on this library.

        Note that this call *may* hang for a bit as it will wait for all
        of a multiline response to return before returning.  This behavior
        is unlikely to ever matter.

        Returns:
            Dictionary mapping package names to dictionary of key-value
            pairs of arguments.  This will smartly handle multiline results.
        """