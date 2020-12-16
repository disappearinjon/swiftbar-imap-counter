#!/usr/bin/env python3
# <bitbar.title>IMAP Counter</bitbar.title>
# <bitbar.author>Jon Lasser</bitbar.author>
# <bitbar.author.github>disappearinjon</bitbar.author.github>
# <bitbar.desc>Count unread IMAP messages in inbox</bitbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>
"""
imap_counter.py is a plugin for SwiftBar, which can be found at

    https://github.com/swiftbar/SwiftBar

It uses a configuration file and queries a remote IMAP server, reporting the
message count in the menu bar.
"""

import configparser
import imaplib
import os
import stat
import sys

# Dict/namespace constants
USERNAME = "username"
PASSWORD = "password"
IMAP_SERVER = "server"
IMAP_PORT = "port"
IMAP_MAILBOX = "mailbox"
USE_SSL = "usessl"
INLINE_TLS = "inlinetls"

# Configuration items
CONFIGFILE = "~/.imap_counterrc"  # no way to override yet
CONFIG_DEFAULTS = {
    IMAP_PORT: 443,
    IMAP_MAILBOX: "INBOX",
    USE_SSL: False,
    INLINE_TLS: False
}

# string constants
OK = "OK"           # used for IMAP response parsing
SERVER = "Server"   # used for config file sections


def getConfig():
    """getConfig gets a configuration from a file and returns it as a dict"""

    # Get path for configuration file
    filename = os.path.expanduser(CONFIGFILE)

    # Need to ensure permissions are 0600 on the file. If not, exit quickly!
    filebits = os.stat(filename)
    if filebits[stat.ST_MODE] & (stat.S_IRWXG | stat.S_IRWXO) > 0:
        sys.stderr.write("Fatal: configuration file {} "
                         "is not limited to user.\n".format(filename))
        sys.exit(1)

    # Read the file
    with open(filename, "r") as configfile:
        config_updates = configfile.read()
        configfile.close()

    # Make a new config
    config = CONFIG_DEFAULTS.copy()
    # Override with changes from config file
    for rawline in config_updates.split("\n"):
        line = rawline.strip()
        if not line:                # ignore blanks
            continue
        if line.startswith("#"):    # ignore comments
            continue
        k, v = line.split("=")
        k = k.strip().lower()
        v = v.strip()

        # Fix our true/false values
        if k == USE_SSL or k == INLINE_TLS:
            if v.lower() in ("1", "true", "on", "yes"):
                v = True
            else:
                v = False

        config[k] = v

    return config


def getMailCount(config):
    """getMailCount takes an IMAP configuration block (say, from getConfig) and
    returns a tuple containing the number of digits, and a list of error
    messages."""
    errors = []

    # Configure SSL if possible, connect to IMAP, and log in
    if config[USE_SSL]:
        imap4 = imaplib.IMAP4_SSL
    else:
        imap4 = imaplib.IMAP4
    with imap4(config[IMAP_SERVER], port=config[IMAP_PORT]) as M:
        # If INLINE_TLS is enabled, go for it. If it fails, die.
        if config[INLINE_TLS]:
            ok, result = M.starttls(ssl_context=None)
            if ok != OK:
                sys.stderr.write("could not start tls: "
                                 "{}: {}\n".format(ok, result))
                sys.exit(1)
        ok, result = M.login(config[USERNAME],
                             config[PASSWORD])
        if ok != OK:
            errors.append("login result: {}: {}".format(ok, result))

        # Select the inbox to count
        ok, result = M.select(config[IMAP_MAILBOX], readonly=True)
        if ok != OK:
            errors.append("select result: {}: {}".format(ok, result))

        # Find unseen messages
        ok, result = M.search(None, 'NOT SEEN')
        if ok != OK:
            errors.append("search result: {}: {}".format(ok, result))

        # Finally we can count our messages
        rawmessages = result[0]
        messages = rawmessages.split()
        M.close()
        M.logout()

    # return the message count and any errors
    return len(messages), errors


def main():

    # Get our configuration
    config = getConfig()

    # Get our mail count
    mailCount, errors = getMailCount(config)

    # Print our result
    if mailCount == 0:
        print(':envelope:')
        print('---')
        print('0 messages')
        print('---')
    else:
        print(':envelope: {} | color=red,yellow'.format(mailCount))
        print('---')
    for line in errors:
        print(line, "| color=red")


if __name__ == "__main__":
    main()
