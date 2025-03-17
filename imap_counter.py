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

from collections import OrderedDict
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
MESSAGE_URL = "message_url"
INLINE_TLS = "inlinetls"
PASSWORD = "password"
UNREAD_LIGHT = "unread_light"
UNREAD_DARK = "unread_dark"
USE_SSL = "usessl"
USERNAME = "username"
RFC_8474 = "rfc_8474"

# Configuration items
CONFIGFILE = "~/.imap_counterrc"  # no way to override yet
CONFIG_DEFAULTS = {
    IMAP_PORT: 443,
    IMAP_MAILBOX: "INBOX",
    USE_SSL: False,
    MAILBOX_URL: "",
    MESSAGE_URL: "",
    INLINE_TLS: False,
    EXPAND: "",  # Expand nothing
    UNREAD_LIGHT: "black",
    UNREAD_DARK: "white",
    RFC_8474: False,  # This will get calculated later
}

# string constants
ALL = "all"  # used for message summarization - summarize all
NEW = "new"  # used for message summarization - summarize new
OK = "OK"  # used for IMAP response parsing
SERVER = "Server"  # used for config file sections
SUBJECT = "Subject: "  # used for mail header parsing
FROMLINE = "From: "  # used for mail header parsing
UTF8CAP = "UTF8=ACCEPT"  # for enabling UTF-8 capability
OBJECTID = "OBJECTID"  # for recognizing ObjectID capability
# strings that all equal "true"
TRUESTRINGS = ("1", "true", "on", "yes")
# strings that all equal "false"
FALSESTRINGS = ("no", "none", "nothing", "false")


def get_config():
    """get_config gets a configuration from a file and returns it as a dict"""

    # Get path for configuration file
    filename = os.path.expanduser(CONFIGFILE)

    # Need to ensure permissions are 0600 on the file. If not, exit quickly!
    filebits = os.stat(filename)
    if filebits[stat.ST_MODE] & (stat.S_IRWXG | stat.S_IRWXO) > 0:
        sys.stderr.write(
            f"Fatal: configuration file {filename} is not limited to user.\n"
        )
        sys.exit(1)

    # Read the file
    with open(filename, "r", encoding="utf-8") as configfile:
        config_updates = configfile.read()
        configfile.close()

    # Make a new config
    config = CONFIG_DEFAULTS.copy()
    # Override with changes from config file
    for rawline in config_updates.split("\n"):
        line = rawline.strip()
        if not line:  # ignore blanks
            continue
        if line.startswith("#"):  # ignore comments
            continue
        key, value = line.split("=")
        key = key.strip().lower()
        value = value.strip()

        # Fix our true/false values
        if key in (USE_SSL, INLINE_TLS):
            value = bool(value.lower() in TRUESTRINGS)
        config[key] = value

    return config


def start_imap(config):
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
            sys.stderr.write(f"could not start tls: {ok}: {result}\n")
            sys.exit(1)
    ok, result = imap.login(config[USERNAME], config[PASSWORD])
    if ok != OK:
        errors.append(f"login result: {ok}: {result}")

    # Enable the UTF-8 capability, but ignore any errors
    try:
        imap.enable(UTF8CAP)
    except imap4.error:
        pass

    return imap, errors


def get_mail_count(imap, config):
    """get_mail_count takes an IMAP connection and a configuration block
    (say, from get_config) and returns a tuple containing the number of
    digits, and a list of error messages."""
    errors = []

    # Select the inbox to count
    ok, result = imap.select(config[IMAP_MAILBOX], readonly=True)
    if ok != OK:
        errors.append(f"select result: {ok}: {result}")

    # Find unseen messages
    ok, result = imap.search(None, "NOT SEEN")
    if ok != OK:
        errors.append(f"search result: {ok}: {result}")

    # Finally we can count our messages
    rawmessages = result[0]
    messages = rawmessages.split()

    # return the message count and any errors
    return len(messages), errors


def decode_header(header):
    """Given the contents of a header (minus the header itself), return
    a string containing the first part of the decoded header.

    This works because subjects return only one part, and the part of From:
    lines that we want (the text name) are the first part of two. This may not
    be a generally extensible strategy."""

    text = 0  # tuple index for the encoded header text
    encoding = 1  # tuple index for the header's encoding
    decoded = email.header.decode_header(header)
    if isinstance(decoded[0][text], bytes):
        if decoded[0][encoding]:
            my_encoding = decoded[0][encoding]
        else:
            my_encoding = "utf-8"
        return decoded[0][text].decode(my_encoding)
    return decoded[0][text]


def decode_message(imap, message_number, rfc_8474):
    """A misnomer, as it's decoding the parts of individual message
    headers that we care about. We need our IMAP connection, a message
    number, and whether or not we should be trying for RFC 8474 object
    IDs in our results.

    We return a message key (either the message number or object ID),
    the From line, the Subject line text, and errors."""
    errors = []
    fromline = ""
    subject = ""

    if rfc_8474:
        ok, data = imap.fetch(message_number, "(EMAILID RFC822.HEADER)")
    else:
        ok, data = imap.fetch(message_number, "(RFC822.HEADER)")
    if ok != OK:
        errors.append(f"failed to get message {message_number}: {data}")

    # There's some work to decode these...
    if "EMAILID" in str(data[0][0]):  # RFC 8474 email ID
        header_parts = str(data[0][0]).split(" ")
        message_key = header_parts[2][1:-1]
    else:
        message_key = message_number
    for item in data:
        if len(item) < 2:  # the closing bit is too short, skip it
            continue
        for line in item[1].decode("utf-8").splitlines():
            if line.strip().startswith(SUBJECT):
                header_len = len(SUBJECT)
                subject = decode_header(line[header_len:])
            if line.strip().startswith(FROMLINE):
                header_len = len(FROMLINE)
                fromline = decode_header(line[header_len:])
    return message_key, fromline, subject, errors


def get_messages(imap, new_only=True, rfc_8474=False):
    """Given an IMAP connection and whether or not to include only new
    messages, return an ordered dict containing each message's subject,
    keyed on message ID if available (and incrementing integers if not)
    and a list of error messages."""
    messages = OrderedDict()
    errors = []

    # Set search type based on what we're expecting to find
    if new_only:
        criterion = "NOT SEEN"
    else:
        criterion = "ALL"

    # Get messages to look at
    ok, result = imap.search(None, criterion)
    if ok != OK:
        errors.append(f"get_messages search result: {ok}: {result}")
        return (messages, errors)

    # Iterate through messages and grab the subjects
    for message_number in result[0].split():
        message_key, fromline, subject, err = decode_message(
            imap, message_number, rfc_8474
        )
        errors.extend(err)
        messages[message_key] = fromline + ": " + subject
    # And go home
    return messages, errors


def stop_imap(imap):
    """Shut down an open IMAP connection. No return value"""
    imap.close()
    imap.logout()


def print_header(config, mail_count):
    """Print the part of the output that appears in the menu bar"""

    # Correct the color names
    light = config[UNREAD_LIGHT].lower()
    dark = config[UNREAD_DARK].lower()

    if mail_count == 0:
        print(":envelope: ")
    else:
        print(
            f":envelope.fill: {mail_count} | color={light},{dark} "
            f"sfcolor={light},{dark}"
        )
    print("---")
    print("Check Mail | refresh=true")
    print("---")


def print_body(imap, config):
    """Given an IMAP and configuration, print the middle section of the menu.
    Return any additional errors."""
    errors = []
    messages = []

    if config[EXPAND]:  # show message summaries
        what = config[EXPAND].strip().lower()
        if what not in FALSESTRINGS:
            if what in (ALL):
                new_only = False
            elif what in (NEW):
                new_only = True
            else:
                new_only = False
                errors.append(f"Do not know how to expand {what} messages")
            messages, newerrs = get_messages(
                imap, new_only=new_only, rfc_8474=config[RFC_8474]
            )
            errors.extend(newerrs)
        for key, value in messages.items():
            if config[RFC_8474]:
                my_url = config[MESSAGE_URL].replace("%s", key)
                print(f"{value} | href={my_url}")
            else:
                print(value)
    else:
        if config[EXPAND] == NEW:
            print("No New Messages")
        elif config[EXPAND] == ALL:
            print("No Messages")

    print("---")
    return errors


def print_footer(errors, config):
    """Print the menu footer"""
    if config[MAILBOX_URL]:
        print(f"Open Mail | href={config[MAILBOX_URL]}")
        print("---")
    for line in errors:
        print(line, "| color=red")


def main():
    """You are here. Do the print stuff, then exit."""

    # Get our configuration
    config = get_config()

    # Log into imap
    imap, errors = start_imap(config)

    # See if we're good to go for RFC 8474
    ok, all_caps = imap.capability()
    if ok != OK:
        errors.append(f"capability result: {ok}: {all_caps}")
    capabilities = str(all_caps[0])
    if OBJECTID in capabilities and config[MESSAGE_URL]:
        config[RFC_8474] = True
    else:
        config[RFC_8474] = False

    # Get our mail count
    mail_count, newerrs = get_mail_count(imap, config)
    errors.extend(newerrs)

    # Print our result
    print_header(config, mail_count)
    errors.extend(print_body(imap, config))
    print_footer(errors, config)

    # Shut down IMAP
    stop_imap(imap)


if __name__ == "__main__":
    main()
