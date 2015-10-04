# Possel

## Running
On linux make sure you have your distribution's equivalent of debian's `libssl-dev` and `libffi-dev` installed. Mac
users should be fine. Windows I have no idea.

Simple steps, assuming you're in a folder with a checkout of both pircel and possel as subfolders (called `pircel` and
`possel`, of course):

    # Make a virtualenv to prevent us dirtying system python packages
    virtualenv -p $(which python3) possel.env
    . possel.env/bin/activate

    # Must install in this order
    pip install -e pircel[bot]
    pip install -e possel

    # Add a user for auth
    python -m possel.auth some_user some_password

    # Run that server
    possel --port 8080 --debug

That last one is the only one you'll need to repeat.

## API Examples with curl

    # A couple of handy shortcuts
    alias post='curl -c possel.cookies -b possel.cookies -H "Content-Type: application/json" -X POST -d'
    alias get='curl -b possel.cookies'

    # You must authenticate before doing *anything* else
    post '{"username": "some_user", "password": "some_password"}' localhost:8080/session

    # Connecting, joining, posting
    post '{"host": "irc.imaginarynet.org.uk", "port": 6697, "secure": true, "nick": "possel", "realname": "Possel IRC", "username": "possel"}' localhost:8080/server
    post '{"server": 1, "name": "#possel-test"}' localhost:8080/buffer
    post '{"buffer": 2, "content": "butts"}' localhost:8080/line

    # Getting lines
    curl localhost:8080/line?id=1
    curl localhost:8080/line?after=10
    curl localhost:8080/line?before=20
    curl localhost:8080/line?last=true

    # Getting buffers
    curl localhost:8080/buffer/1
    curl localhost:8080/buffer/all

    # Getting servers
    curl localhost:8080/server/1
    curl localhost:8080/server/all

## Discussion

We're on IRC! Server: `irc.imaginarynet.uk`, channel: `#possel`.
