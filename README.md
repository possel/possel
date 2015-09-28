# Possel

## Running
Simple steps, assuming you're in a folder with a checkout of both pircel and possel as subfolders (called `pircel` and
`possel`, of course):

    virtualenv -p $(which python3) possel.env
    . possel.env/bin/activate
    pip install -e pircel
    pip install -e possel
    python -m possel.resources

That last one is the only one you'll need to repeat.

## Discussion

We're on IRC! Server: `irc.imaginarynet.uk`, channel: `#possel`.
