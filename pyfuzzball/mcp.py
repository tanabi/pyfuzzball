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
    # What MCP protocol version do we support?
    PROTOCOL_VERSION = "2.1"

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
            mcp_proto = self.readline(10).strip()
            tries = tries + 1

        if tries >= 3:
            raise RuntimeError("No response from MUCK server.")

        res = re.match(r'#\$#mcp version: "([\d.]+)" to: "([\d.]+)"',
                       mcp_proto
        )

        if not res:
            raise RuntimeError("MCP header not found on MUCK login screen.")

        # Make sure our protocol version is supported.
        #
        # In English, if the oldest supported server protocol us newer than
        # our supported protocol, or if the newest supported protocol is
        # older than our supported protocol.
        if self.version_compare(res.group(1), self.PROTOCOL_VERSION) == 1 or \
           self.version_compare(self.PROTOCOL_VERSION, res.group(2)) == 1:
            raise RuntimeError("Server supports protocols %s to %s - "
                               "we support protocol %s" %
                               (res.group(1), res.group(2),
                                self.PROTOCOL_VERSION)
            )

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
            % (self.auth, self.PROTOCOL_VERSION, self.PROTOCOL_VERSION)
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
                self.catalog[matches.group(1)] = (matches.group(2), 
                                                  matches.group(3))

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
        return str(random.randint(100000, 1000000))

    def version_compare(self, v1, v2):
        """This compares version 1 and version 2.  Returns in the
        following fashion:

        -1 if v1 < v2
        0 if v1 == v2
        1 if v1 > v2

        Arguments:
            v1: str in the format of X.Y
            v2: str in the format of X.Y

        Returns:
            Integer as indicated above
        """

        v1_major, v1_minor = v1.split('.', 1)
        v2_major, v2_minor = v2.split('.', 1)

        v1_major = int(v1_major)
        v2_major = int(v2_major)
        v1_minor = float(v1_minor) # In case of multiple decimals
        v2_minor = float(v2_minor)

        if v1_major > v2_major:
            return 1
        elif v1_major < v2_major:
            return -1
        elif v1_minor > v2_minor:
            return 1
        elif v1_minor < v2_minor:
            return -1
        else:
            return 0

    def escape(self, txt):
        """Does MCP escaping on " and backslash for a given text block, and
        returns the escaped text.

        Arguments:
            txt: str, the text to escape

        Returns:
            str, escaped text
        """

        return txt.replace("\\", "\\\\").replace('"', '\\"')

    def unescape(self, txt):
        """Removes escape characters for a given text block

        Arguments:
            txt: str, the text to remove escapes

        Returns:
            str, unescaped text
        """

        return txt.replace("\\\\", "\\").replace('\\"', '"')

    def call(self, package, message="", arguments={}, min_version=None,
             max_version=None):
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
            message: str with an optional "message".  Messages are like RPC
                     functions for a given package.
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

        if message:
            buf.write('#$#%s-%s %s' % (package, message, self.auth))
        else:
            buf.write('#$#%s %s' % (package, self.auth))

        for key, val in arguments.items():
            if isinstance(val, list):
                need_data_tag = True
                buf.write(' %s*: ""' % key)
            else:
                buf.write(' %s: "%s"' % (key, self.escape(val)))

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

    def process(self):
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
            Tuple, first entry:

            Dictionary mapping package names to dictionary with keys
            of 'message' and 'parameters'.  This will smartly handle
            multiline results which will be arrays in parameters.

            Second entry:

            Any lines we could not process.  They will appear in order
            that we found them, but it will be impossible to tell what
            MCP calls happened between the unknown lines.  You can usually
            ignore this unless you want them for a particular reason.
        """

        lines = []

        while True:
            line = self.readline(0.25)

            if not line:
                break

            lines.append(line)

        # We got nothing if there are no lines
        if not lines:
            return ({}, [])

        return_value = {}
        unknown_lines = []

        # To support multi-line
        current_req = {}
        multi_liners = []
        data_tag = ""

        # NOTE: In general, this library is not very tolerant of extra
        # spaces.  This particular block is a serious offender.
        #
        # TODO: Make this library, generally, more accepting of extra
        # spaces in an MCP line.
        for line in lines:
            # Only process MCP lines
            if line[0:3] != '#$#':
                unknown_lines.append(line)
                continue

            # Are we in a multi-line block?
            #
            # TODO: This actually very brittle. According to
            # the MCP specification, we can get other messages in the
            # middle of receiving a multi-line block.
            #
            # Actually this whole method should probably be refactored,
            # I'm not happy with any of this code.
            if multi_liners:
                # This will either be a #$#* or a #$#: line
                if line[3] == '*':
                    meta, value = line.split(":", 1)

                    meta_details = meta.split(" ")

                    # this should match data tag
                    #
                    # So ... FuzzBall is an asshole :)  It will
                    # provide a _data-tag such as: BF2547A
                    #
                    # Then it will randomly decide, hey, let's
                    # add some 0's in there when we actually use it,
                    # such as: 0BF2547A
                    #
                    # This is a bug, but means we can't match data_tag
                    # exactly.
                    if data_tag != meta_details[1]:
                        print("Multi liner no data tag")
                        unknown_lines.append(line)
                        continue

                    # This should be a multi-liner field
                    if meta_details[2] not in multi_liners:
                        print("Multi liner unknown field")
                        unknown_lines.append(line)
                        continue

                    current_req['parameters'][meta_details[2]].append(
                        value[1:] # Drop leading space
                    )
                elif line[3] == ':':
                    # End
                    multi_liners = []

                    if current_req['package'] in return_value:
                        return_value[current_req['package']].append({
                            'message': current_req['message'],
                            'parameters': current_req['parameters']
                        })
                    else:
                        return_value[current_req['package']] = [{
                            'message': current_req['message'],
                            'parameters': current_req['parameters']
                        }]

                continue

            parts = line[3:].split(" ", 2)

            # Package parts[0], auth token should be parts[1], and
            # the parameters are parts[2].  parts[2] may not exist.
            if parts[1] != self.auth:
                # This should always match -- if it does not, ignore it.
                print("Auth did not match")
                unknown_lines.append(line)
                continue

            # See what package parts[0] belongs to.  parts[0] may have
            # a suffix.  For instance:
            #
            # mcp-negotiate  <- package name
            # mcp-negotiate-can <- package name with suffix
            potential_matches = []

            for package in self.catalog:
                if parts[0].startswith(package + "-"):
                    potential_matches.append(package)

            if not len(potential_matches):
                # Non-negotiated package -- treat this as invalid.
                print("Non-negotiated package")
                unknown_lines.append(line)
                continue

            # One of two things may happen:
            #
            # 1. We have only 1 potential match -- that's the package
            #    we want.
            # 2. We have multiple potential matches.  see if we have
            #    an exact match (the package we want) otherwise just
            #    pick the first package
            desired_package = potential_matches[0]

            if len(potential_matches) > 1:
                for package in potential_matches:
                    if package == parts[0]:
                        desired_package = parts[0]
                        break

            # If desired package isn't a match for parts[0], then
            # we have a mesg component.
            mesg = ""

            if desired_package != parts[0]:
                mesg = parts[0][len(desired_package)+1:]

            # We have package, message, and any arguments.
            # Now we need to see if we are multi-line or not.
            parameters = {}

            if not len(parts[2]): # We're done!
                if desired_package in return_value:
                    return_value[desired_package].append({
                        "message": mesg,
                        "parameters": {}
                    })
                else:
                    return_value[desired_package] = [{
                        "message": mesg,
                        "parameters": {}
                    }]

                continue

            # The remaining processing needs to be done like a state
            # machine due to the escaping.  Its pretty annoying.  There
            # is probably a better way to do this.
            key = ""
            value = ""
            is_escaped = False
            key_accumulate = True
            in_quote = False

            for x in parts[2].strip():
                if key_accumulate:
                    if x == ':':
                        # Key is done
                        key_accumulate = False
                    else:
                        if x == ' ' and not key:
                            # Skip space
                            continue

                        key += x
                else:
                    # Accumulating value
                    if not in_quote:
                        if x == '"': # Entering quote
                            in_quote = True
                        elif x != ' ' and key == "_data-tag":
                            # data tag doesn't always have quotes.
                            in_quote = True
                            value = x

                        # Technically, this is "too tolerant" of errors,
                        # because we are ignoring any non-quotes, but I'm
                        # not sure I care.
                        continue
                    else:
                        # We are either in an escape sequence or not.
                        if is_escaped:
                            # This character, be it a \ or a ", goes
                            # into the value
                            value += x
                            is_escaped = False
                        else:
                            # Are we starting an escape sequence?
                            if x == '\\':
                                is_escaped = True
                                continue
                            elif x == '"': # We've ended our parameter.
                                key_accumulate = True
                                in_quote = False

                                # Is it a multi-line field?
                                if key[-1:] == "*" :
                                    key = key[:-1]
                                    multi_liners.append(key)

                                    parameters[key] = []
                                else:
                                    parameters[key] = value

                                key = ""
                                value = ""
                            elif x.isspace() and key == "_data-tag":
                                # Data tag doesn't always have quotes.
                                in_quote = False
                                key_accumulate = True

                                parameters[key] = value
                                key = ""
                                value = ""
                            else:
                                # Add it to the value
                                value += x

            # data-tag is a pain in the ass.  Doesn't have quotes around
            # it.  Its usually the last thing on the line, so we need to do
            # some cleanup  if its the last thing in our state machine.
            if key == "_data-tag":
                in_quote = False
                key_accumulate = True
                parameters[key] = value
                key = ""
                value = ""


            # Let's see if our state machine is in a weird state.
            if not key_accumulate or in_quote or is_escaped:
                # This is a weird line, let's drop it.
                print("Weird line")
                print(key_accumulate)
                print(in_quote)
                print(is_escaped)
                print(line)
                unknown_lines.append(line)
                continue

            # If we have a multi-line field, we better have _data-tag
            if len(multi_liners):
                if '_data-tag' not in parameters:
                    print("data tag not provided")
                    unknown_lines.append(line)
                else:
                    # We need to read our multi-lines
                    data_tag = parameters['_data-tag']
                    current_req = {
                        "package": desired_package,
                        "message": mesg,
                        "parameters": parameters
                    }
            else:
                if desired_package in return_value:
                    return_value[desired_package].append(
                        {
                            "message": mesg,
                            "parameters": parameters
                        }
                    )
                else:
                    return_value[desired_package] = [{
                        "message": mesg,
                        "parameters": parameters
                    }]

        # do we still have multi-liners to read?
        # I really need to join this code with the code in the loop,
        # this is messy.
        #
        # But this whole method is super messy.
        while multi_liners:
            line = self.readline(0.2)

            # Only process MCP lines
            if line[0:3] != '#$#':
                continue

            # This will either be a #$#* or a #$#: line
            if line[3] == '*':
                meta, value = line.split(":", 1)

                meta_details = meta.split(" ")

                # this should match data tag
                if meta_details[1] != data_tag:
                    unknown_lines.append(line)
                    continue

                # This should be a multi-liner field
                if meta_details[2] not in multi_liners:
                    unknown_lines.append(line)
                    continue

                current_req['parameters'][meta_details[2]].append(
                    value[1:] # Drop leading space
                )
            elif line[3] == ':':
                # End
                multi_liners = []

                if current_req['package'] in return_value:
                    return_value[current_req['package']].append({
                        'message': current_req['message'],
                        'parameters': current_req['parameters']
                    })
                else:
                    return_value[current_req['package']] = [{
                        'message': current_req['message'],
                        'parameters': current_req['parameters']
                    }]

        return (return_value, unknown_lines)
