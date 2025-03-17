# swiftbar-imap-counter

An IMAP counter plugin for [SwiftBar](https://github.com/swiftbar/SwiftBar)
by Jon Lasser <jon@lasser.org>

This project is under an MIT license. See [the license](./LICENSE)
for specifics.

# Requirements
* SwiftBar (Currently testing on 2.0.1.)
* Python 3.8.1 or newer (Currently testing on Python 3.11). May work
  just fine with earlier releases as far back as 3.6, but development
  environments require 3.8.1 or newer.

# Installation

1. If you do not have Python on your Mac, install it. You can use the
   [official packages](https://docs.python.org/3/using/mac.html),
   [MacPorts](https://www.macports.org), [Homebrew](https://brew.sh), or
   any other method that results in Python being in your path. I haven't
   tried them yet, but
   [these instructions](https://medium.com/marvelous-mlops/the-rightway-to-install-python-on-a-mac-f3146d9d9a32)
   appear promising. 
1. Install [SwiftBar](https://github.com/swiftbar/SwiftBar)
1. Unpack swiftbar-imap-counter in an appropriate place
1. `cd` into the directory where you have unpacked swiftbar-imap-counter
1. Copy *imap_counterrc.EXAMPLE* to *$HOME/.imap_counterrc*:
   `cp imap_counterrc.EXAMPLE ~/.imap_counterrc`
1. Change the permissions on `.imap_counterrc` to 0600:
   `chmod 0600 ~/.imap_counterrc`
1. Edit *$HOME/.imap_counterrc* for your specific IMAP configuration. At a
   minimum, you will need to update the server, username, and password.
   Many third-party providers (e.g., [FastMail](https://fastmail.com/)
   may have specific instructions, and some will require an
   application-specific password. Even if it's optional, you should
   probably enable SSL or TLS, depending on what your provider has
   available. (NOTE: I don't have a mail server that allows me to test
   inline TLS, so that support is speculative.)
1. Link *imap_counter.py* to your SwiftBar plugin directory with a
   filename that indicates the frequency with which to check for mail
   updates.  For example, if your SwiftBar plugin directory is in
   *$HOME/Documents/SwiftBar* and you want to run at 15 minute
   intervals:
   `ln -s imap_counter.py ~/Documents/SwiftBar/imap-counter.15m.py`

# Use

It sits there in your menu bar and tells you how many messages you've
got. You can see a list of messages when you've clicked the dropdown,
depending on your *expand* setting, as well as refresh your message
counter and (if *mailbox_url* is set) open your inbox directly.

You can also set a configuration option that will change the color of the
icon and count in the menu bar when mail is received.

# Getting Help

You can mail me at my address above, or
[file an issue in GitHub](https://github.com/disappearinjon/swiftbar-imap-counter/issues).
Some mail problems may be beyond my ability to resolve, but I'll do my
best to help!

# Helping Me (Development Instructions)

I've put some features I'd like to implement in the *TODO* file. Pull
requests gladly accepted!

The imap counter uses [Poetry](https://python-poetry.org) to manage
dependencies. If you do not already have poetry installed, you can
install it with

    pip install --user poetry

or other incantations, depending on your package manager. (Note that
MacPorts does not include `pip` in its default Python package, and you
will have to install pip separately.)

Once Poetry is installed, you can install the current versions of the
development tools by running the following from the
`swiftbar-imap-counter` directory:

    poetry install --with dev

To enter the virtual environment and use the dev tools, run

    $(poetry env activate)

from the `swiftbar-imap-counter` directory. (The above works in bash and
zsh; if you are using a different shell, try surrounding the "poetry env
activate" in backticks instead.)

You can now run `black`, `flake8`, and `pylint` to format your code and
validate it. I aim for perfect scores in flake8 and pylint, though it's
true that some exceptions may be necessary.

I have included a Git pre-commit hook to enforce quality checks as
`pre-commit.EXAMPLE`. To install, copy it to `.git/hooks/pre-commit` and
ensure it is executable.

As always, I'm happy to assist with configuration or code validation if
I can!
