"use strict";

var possel = {
  get_users: function(id){
    return $.get("/user/" + id);
  },
  get_buffer: function(id){
    return $.get("/buffer/" + id);
  },
  get_line_by_id: function(id){
    return $.get("/line?id=" + id);
  },
  get_last_line: function(){
    return $.get("/line?last=true");
  },
  send_line: function(buffer, content){
    $.ajax({
      type: 'POST',
      url: '/line',
      data: JSON.stringify({ buffer: buffer,
                             content: content
                           }),
      contentType: 'application/json'
    });
  }
};

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
      if (last_line_data.length == 0) {
        console.warn("no lines found.");
        return 0;
      }
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
                possel.get_line_by_id(msg.line).then(function(data) {
                    var line = data[0];
                    new_line(line);
                });
                break;
            case "buffer":
                possel.get_buffer(msg.buffer).then(function(buffer_data){
                    new_buffer(buffer_data[0]);
                });
                break;
        }
    }

    $('#message-input-form').submit(function(event) {
      event.preventDefault();
      var message = $('#message-input').val();
      var buffer_id = $('.buffer.active')[0].id;
      possel.send_line(buffer_id, message);
      $('#message-input').val('');
    });

    $.when(possel.get_users("all"),
          possel.get_buffer("all"),
          possel.get_last_line()
         )
        .done(function(user_data, buffer_data, last_line_data){
            user_data[0].forEach(function(user){
                users[user.id] = user;
            });
            buffer_data[0].forEach(function(buffer) {
                new_buffer(buffer);
            });
            var ws = new ReconnectingWebSocket(ws_url);
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
