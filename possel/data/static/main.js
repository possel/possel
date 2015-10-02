function get_user(id){
    return $.get("/user/" + id);
}

function get_buffer(id){
    return $.get("/buffer/" + id);
}

function get_line_by_id(id){
    return $.get("/line?id=" + id);
}

function get_last_line(){
    return $.get("/line?last=true");
}

function send_line(buffer, content){
    $.ajax({
      type: 'POST',
      url: '/line',
      data: JSON.stringify({ buffer: buffer,
              content: content
            }),
      contentType: 'application/json'
    });
}

$(function(){
    var users = [], buffers = [];

    function new_line(line){
        var buffer = buffers[line.buffer], user = users[line.user];
        $("#" + buffer.id).append("<div class=\"buffer-line\"><span class=\"date column\">" + moment(line.timestamp).format("hh:mm:ss")
                                  + "</span><span class=\"nick column mid-column\">" + user.nick
                                  + "</span><span class=\"message column mid-column\">" + line.content + "</span></div>");
    }

    function buffer_maker(){
      var first = true;

      var inner_func = function(buffer){
          buffers[buffer.id] = buffer;
        var active_class = first?' active':'';
        first = false;
        $("#bufferlist").append('<li role="presentation" class="' + active_class + '">'
                                + '<a href="#' + buffer.id + '" role="tab" data-toggle="tab" aria-controls="' + buffer.id + '">'
                                + buffer.name
                                + '</a></li>');
        $("#message-pane").append('<div id="' + buffer.id + '" class="buffer tab-pane' + active_class + '" role="tabpanel"></div>');
      }
      return inner_func;
    }
    var new_buffer = buffer_maker();

    function prepopulate_lines(last_line_data, nlines){
        var last_line = last_line_data[0];
        $.get("/line?after=" + (last_line.id - nlines)).then(function(lines){
            lines.forEach(function(line){
                new_line(line);
            });
        });
    }

    function handle_push(event){
        var msg = JSON.parse(event.data);
        console.log(msg);
        switch(msg.type){
            case "line":
                get_line_by_id(msg.line).then(function(data) {
                    var line = data[0];
                    new_line(line);
                });
                break;
            case "buffer":
                get_buffer(msg.buffer).then(function(buffer_data){
                    new_buffer(buffer_data[0]);
                });
                break;
        }
    }

    $('#message-input-form').submit(function(event) {
      event.preventDefault();
      var message = $('#message-input').val();
      var buffer_id = $('.buffer.active')[0].id;
      send_line(buffer_id, message);
      $('#message-input').val('');
    });

    $.when(get_user("all"),
          get_buffer("all"),
          get_last_line()
         )
        .done(function(user_data, buffer_data, last_line_data){
            user_data[0].forEach(function(user){
                users[user.id] = user;
            });
            buffer_data[0].forEach(function(buffer) {
                new_buffer(buffer);
            });
            var ws = new WebSocket(ws_url);
            ws.onopen = function() {
                console.log("connected");
            };
            ws.onclose = function() {
                console.log("disconnected");
            };
            ws.onmessage = handle_push;
            prepopulate_lines(last_line_data[0], 30);
        });
});
