"use strict";

var possel = {
  get_users: function(id){
    return $.get("/user/" + id);
  },
  events: {
    submit_event: function(node) {
      $(node).submit(function(event) {
        event.preventDefault();
        var message = $('#message-input').val();
        var buffer_id = $('.buffer.active')[0].id;
        possel.send_line(buffer_id, message).then(function(){
          $('#message-input').val('');
        });
      });
    }
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
    return $.ajax({
      type: 'POST',
      url: '/line',
      data: JSON.stringify({ buffer: buffer,
                             content: content
                           }),
      contentType: 'application/json'
    });
  }
};

var util = {
  node: function(elem, val, attrs) {
    var element = $("<" + elem + ">");
    if (val instanceof Array) {
      for(var i in val) {
        element.append(val[i]);
      }
    } else {
      element.html(val);
    }
    if (attrs !== undefined) {
      var keys = Object.keys(attrs);
      for(var a in keys) {
        element.attr(keys[a], attrs[keys[a]]);
      }
    }
    return element;
  }
}

$(function(){
  var users = [], buffers = [];

  function new_line(line){
    var buffer = buffers[line.buffer], user = users[line.user];
    $("#" + buffer.id).append(
      util.node("div",
                [moment(line.timestamp).format("hh:mm:ss"),
                 util.node("span", user.nick, {
                   class: "nick column mid-column"
                 })
                 , util.node("span", line.content, {
                   class: "message column mid-column"
                 })],
                       {
                         class: "buffer-line"
                       }));
  }

  function buffer_maker(){
    var first = true;
    var inner_func = function(buffer){
      buffers[buffer.id] = buffer;
      var active_class = first?' active':'';
      first = false;
      $("#bufferlist").append(
        util.node("li",
                         util.node("a",
                                          buffer.name, {
                                            href: "#" + buffer.id,
                                            role: "tab",
                                            "data-toggle": "tab",
                                            "aria-controls": buffer.id
                                          }), {
                           role: "presentation",
                           class: active_class
                         }
                        )
      );
      $("#message-pane").append(
        util.node("div", null, {
          id: buffer.id,
          class: "buffer tab-pane " + active_class,
          role: "tabpanel"
        }));
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
    case "user":
      get_user(msg.user).then(function(user_data){
        var user = user_data[0];
        users[user.id] = user;
      });
    }
  }

  possel.events.submit_event('#message-input-form');
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
