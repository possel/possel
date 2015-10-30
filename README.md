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
    pip install -e pircel
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
    curl localhost:8080/line?last=10
    curl localhost:8080/line?buffer=3

    # Combining filters in getting lines
    curl localhost:8080/line?buffer=3&last=20
    curl localhost:8080/line?after=10&before=20

    # Getting buffers
    curl localhost:8080/buffer/1
    curl localhost:8080/buffer/all

    # Getting servers
    curl localhost:8080/server/1
    curl localhost:8080/server/all

## The Websocket
Real time notifications are achieved with a websocket which you can connect to with the following javascript (you'll
need to find a websocket client for the language you're working in):

    var ws = new ReconnectingWebSocket(ws_url);
    ws.onopen = function() {
      console.log("connected");
    };
    ws.onclose = function() {
      console.log("disconnected");
    };
    ws.onmessage = function(event){
      console.log(JSON.parse(event.data));
    };

And following are examples of the kinds of messages you can expect from the websocket (you shouldn't send anything to
it).

    {"line": 1036, "type": "last_line"}  # Sent on connect, indicates the highest line id at that point
    {"server": 2, "type": "server"}  # We're connected to a new server
    {"server": 1, "buffer": 4, "type": "buffer"}  # We've joined a buffer

    {"user": 11, "server": 1, "type": "user"}  # A new user has been discovered (cache them please)
    {"user": 1, "buffer": 4, "membership": 14, "type": "membership"}  # User with id 1 has joined buffer 4
    {"membership": {"buffer": 3, "id": 17, "user": 11}, "type": "delete_membership"}  # A user has left a channel (should probably standardise this with the join one)

    {"line": 1037, "buffer": 3, "type": "line"}  # a wild line has appeared

## Discussion

We're on IRC! Server: `irc.imaginarynet.uk`, channel: `#possel`.
