# pyfuzzball
Python Library for Interacting with Fuzzball MUCKs

# Design Notes
The library should provide a low level interface to connect to the MUCK and do the nasty socket stuff and conversion of proper strings to binary so that the library user doesn't have to worry about such things.

It should provide an interface to log in and 'play' the MUCK as well as to use MCP.

'Playing' the MUCK should provide a simple stream interface to read and write stuff from the MUCK.  What is provided should be strings with the option of stripping out ANSI crap.

MCP should provide an API-like interface with the following features:

- Authentication
- Negotiation
- Trigger event
- Clean up / exit nicely
