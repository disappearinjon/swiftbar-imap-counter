#!/usr/bin/env PYTHONIOENCODING=UTF-8 python3
# <bitbar.title>IMAP Counter</bitbar.title>
# <bitbar.version>1.1.1</bitbar.version>
# <bitbar.author>Jon Lasser</bitbar.author>
# <bitbar.author.github>disappearinjon</bitbar.author.github>
# <bitbar.desc>Count unread IMAP messages in inbox</bitbar.desc>
# <bitbar.abouturl>https://github.com/disappearinjon/swiftbar-imap-counter</bitbar.abouturl>
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
import email.header
import imaplib
import os
import stat
import sys

# Dict/namespace constants
EXPAND = "expand"
IMAP_SERVER = "server"
IMAP_PORT = "port"
IMAP_MAILBOX = "mailbox"
MAILBOX_URL = "mailbox_url"
INLINE_TLS = "inlinetls"
PASSWORD = "password"
UNREAD_LIGHT = "unread_light"
UNREAD_DARK = "unread_dark"
USE_SSL = "usessl"
USERNAME = "username"

# Configuration items
CONFIGFILE = "~/.imap_counterrc"  # no way to override yet
CONFIG_DEFAULTS = {
    IMAP_PORT: 443,
    IMAP_MAILBOX: "INBOX",
    USE_SSL: False,
    MAILBOX_URL: "",
    INLINE_TLS: False,
    EXPAND: "",      # Expand nothing
    UNREAD_LIGHT: "black",
    UNREAD_DARK: "white"
}

# string constants
ALL = "all"              # used for message summarization - summarize all
NEW = "new"              # used for message summarization - summarize new
OK = "OK"                # used for IMAP response parsing
SERVER = "Server"        # used for config file sections
SUBJECT = "Subject: "    # used for mail header parsing
FROMLINE = "From: "      # used for mail header parsing
UTF8CAP = "UTF8=ACCEPT"  # for enabling UTF-8 capability
# strings that all equal "true"
TRUESTRINGS = ("1", "true", "on", "yes")
# strings that all equal "false"
FALSESTRINGS = ("no", "none", "nothing", "false")


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
            if v.lower() in TRUESTRINGS:
                v = True
            else:
                v = False

        config[k] = v

    return config


def startIMAP(config):
    """Start an IMAP session, enable TLS or SSL if available,
    and then log in.

    Return a tuple containing the IMAP object, and any errors."""

    errors = []

    # Configure SSL if possible, connect to IMAP, and log in
    if config[USE_SSL]:
        imap4 = imaplib.IMAP4_SSL
    else:
        imap4 = imaplib.IMAP4
    imap = imap4(config[IMAP_SERVER], port=config[IMAP_PORT])

    # If INLINE_TLS is enabled, go for it. If it fails, die.
    if config[INLINE_TLS]:
        ok, result = imap.starttls(ssl_context=None)
        if ok != OK:
            sys.stderr.write("could not start tls: "
                             "{}: {}\n".format(ok, result))
            sys.exit(1)
    ok, result = imap.login(config[USERNAME],
                            config[PASSWORD])
    if ok != OK:
        errors.append("login result: {}: {}".format(ok, result))

    # Enable the UTF-8 capability, but ignore any errors
    try:
        imap.enable(UTF8CAP)
    except imaplib.error:
        pass

    return imap, errors


def getMailCount(imap, config):
    """getMailCount takes an IMAP connection and a configuration block
    (say, from getConfig) and returns a tuple containing the number of
    digits, and a list of error messages."""
    errors = []

    # Select the inbox to count
    ok, result = imap.select(config[IMAP_MAILBOX], readonly=True)
    if ok != OK:
        errors.append("select result: {}: {}".format(ok, result))

    # Find unseen messages
    ok, result = imap.search(None, 'NOT SEEN')
    if ok != OK:
        errors.append("search result: {}: {}".format(ok, result))

    # Finally we can count our messages
    rawmessages = result[0]
    messages = rawmessages.split()

    # return the message count and any errors
    return len(messages), errors


def decodeHeader(header):
    """Given the contents of a header (minus the header itself), return
    a string containing the first part of the decoded header.

    This works because subjects return only one part, and the part of From:
    lines that we want (the text name) are the first part of two. This may not
    be a generally extensible strategy."""

    TEXT = 0      # tuple index for the encoded header text
    ENCODING = 1  # tuple index for the header's encoding
    decoded = email.header.decode_header(header)
    if isinstance(decoded[0][TEXT], bytes):
        return decoded[0][TEXT].decode(decoded[0][ENCODING])
    else:
        return decoded[0][TEXT]


def getMessages(imap, newOnly=True):
    """Given an IMAP connection and whether or not to include only new
    messages, return a tuple containing a list of message subjects and
    a list of error messages."""
    messages = []
    errors = []

    # Set search type based on what we're expecting to find
    if newOnly:
        criterion = "NOT SEEN"
    else:
        criterion = "ALL"

    # Get messages to look at
    ok, result = imap.search(None, criterion)
    if ok != OK:
        errors.append("getMessages search result: {}: {}".format(ok, result))
        return (messages, errors)

    # Iterate through messages and grab the subjects
    for messageNumber in result[0].split():
        ok, data = imap.fetch(messageNumber, '(RFC822.HEADER)')
        if ok != OK:
            errors.append("failed to get message {}: {}".format(messageNumber,
                                                                data))
        # There's some work to decode these...
        for item in data:
            if len(item) < 2:       # the closing bit is too short, skip it
                continue
            fromline = ""
            subject = ""
            for line in item[1].decode("utf-8").splitlines():
                if line.strip().startswith(SUBJECT):
                    subject = decodeHeader(line[len(SUBJECT):])
                if line.strip().startswith(FROMLINE):
                    fromline = decodeHeader(line[len(FROMLINE):])
            messages.append(fromline + ": " + subject)
    # And go home
    return messages, errors


def stopIMAP(imap):
    """Shut down an open IMAP connection. No return value"""
    imap.close()
    imap.logout()
    return


def printHeader(config, mailCount):
    """Print the part of the output that appears in the menu bar"""

    # Correct the color names
    light = config[UNREAD_LIGHT].lower()
    dark = config[UNREAD_DARK].lower()

    if mailCount == 0:
        print(':envelope: ')
    else:
        print(':envelope.fill: {} | color={},{} '
              'sfcolor={},{}'.format(mailCount,
                                     light, dark, light, dark))
    print('---')
    print('Check Mail | refresh=true')
    print('---')
    return


def printBody(count, imap, config):
    """Given an IMAP and configuration, print the middle section of the menu.
    Return any additional errors."""
    errors = []
    messages = []

    if config[EXPAND]:    # show message summaries
        what = config[EXPAND].strip().lower()
        if what not in FALSESTRINGS:
            if what in (ALL):
                newOnly = False
            elif what in (NEW):
                newOnly = True
            else:
                errors.append('Do not know how to expand '
                              '{} messages'.format(what))
            messages, newerrs = getMessages(imap, newOnly=newOnly)
            errors.extend(newerrs)
    if len(messages):
        for item in messages:
            print(item)
    else:
        if config[EXPAND] == NEW:
            print('No New Messages')
        elif config[EXPAND] == ALL:
            print('No Messages')

    print('---')
    return errors


def printFooter(errors, config):
    """Print the menu footer"""
    if config[MAILBOX_URL]:
        print('Open Mail | href={}'.format(config[MAILBOX_URL]))
        print('---')
    for line in errors:
        print(line, '| color=red')


def main():
    """You are here. Do the print stuff, then exit."""

    # Get our configuration
    config = getConfig()

    # Log into imap
    imap, errors = startIMAP(config)

    # Get our mail count
    mailCount, newerrs = getMailCount(imap, config)
    errors.extend(newerrs)

    # Print our result
    printHeader(config, mailCount)
    errors.extend(printBody(mailCount, imap, config))
    printFooter(errors, config)

    # Shut down IMAP
    stopIMAP(imap)


if __name__ == "__main__":
    main()
