# Possel

## Running
Simple steps, assuming you're in a folder with a checkout of both pircel and possel as subfolders (called `pircel` and
`possel`, of course):

    virtualenv -p $(which python3) possel.env
    . possel.env/bin/activate
    pip install -e pircel
    pip install -e possel
    possel --port 8080 --debug

That last one is the only one you'll need to repeat.

## API Examples with curl

    alias post='curl -H "Content-Type: application/json" -X POST -d'

    # Connecting, joining, posting
    post '{"host": "irc.imaginarynet.org.uk", "port": 6697, "secure": true, "nick": "possel", "realname": "Possel IRC", "username": "possel"}' localhost:8080/server
    post '{"server": 1, "name": "#possel-test"}' localhost:8080/buffer
    post '{"buffer": 1, "content": "butts"}' localhost:8080/line

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
