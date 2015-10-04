"use strict";

var possel = {
  get_user: function(id){
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
  },
  login: function(username, password){
    var data = JSON.stringify({username: username, password: password});
    return $.ajax({
      type: 'POST',
      url: '/session',
      data: data,
      contentType: 'application/json'
    });
  },
  verify_token: function(){
    return $.ajax({
      type: 'GET',
      url: '/session',
    });
  },
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


  function scroll_to_bottom(element){
    element.scrollTop(element.prop('scrollHeight'));
  }

  function new_line(line){
    var buffer = buffers[line.buffer], user = users[line.user];
    $("#" + buffer.id).append(
      util.node("div",
                [util.node("span",
                           moment.unix(line.timestamp).format("hh:mm:ss"), {
                             class: "date column"
                           }),
                 util.node("span", line.nick, {
                   class: "nick column mid-column"
                 })
                 , util.node("span", line.content, {
                   class: "message column mid-column"
                 })],
                {
                  class: "buffer-line"
                }));
    scroll_to_bottom($('#message-pane'));
  }

  function new_buffer(buffer){
      var buffer_link, parent_node;
      console.log(buffer);
      buffers[buffer.id] = buffer;
      switch(buffer.kind){
        case "system":
          parent_node = $('#bufferlist');
          parent_node.append(
              util.node('li',
                util.node('a', buffer.name, {
                  href: '#' + buffer.id,
                  role: 'tab',
                  'data-toggle': 'tab',
                  'aria-controls': buffer.id,
                }), {
                  role: 'presentation',
                  id: 'server-buffer-link-' + (buffer.server?buffer.server:'root'),
                  'class': 'nav-buffer-system',
                }
              ));
          break;
        case "normal":
          parent_node = $('#server-buffer-link-' + buffer.server)
          parent_node.after(
            util.node("li",
                      util.node("a",
                                buffer.name, {
                                  href: "#" + buffer.id,
                                  role: "tab",
                                  "data-toggle": "tab",
                                  "aria-controls": buffer.id
                                }), {
                                  role: "presentation",
                                  'class': 'nav-buffer-normal',
                                }
                     )
          );
          break;
      }
      $("#message-pane").append(
        util.node("div", null, {
          id: buffer.id,
          class: "buffer tab-pane",
          role: "tabpanel"
        }));
      buffer_link = $('#bufferlist a[href="#' + buffer.id + '"]');
      buffer_link.on('shown.bs.tab', function(event){
        scroll_to_bottom($('#message-pane'));
      });
      buffer_link.tab('show');
  }

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
    console.log(event.data);
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
      possel.get_user(msg.user).then(function(user_data){
        var user = user_data[0];
        users[user.id] = user;
      });
    }
  }

  function init(){
    console.log('Initializing');
    possel.events.submit_event('#message-input-form');
    $.when(possel.get_user("all"),
        possel.get_buffer("all"),
        possel.get_last_line()
        )
      .done(function(user_data, buffer_data, last_line_data){
        console.log('done preparing');
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
        prepopulate_lines(last_line_data[0], 3000);
      });
  }

  function do_login(){
    $('#login-modal').modal('show');
    $('#login-submit').on('click', function(event){
        var username = $('#login-username').val(), password = $('#login-password').val();
        possel.login(username, password).done(init);
    });
  }

  if(Cookies.get('token')){
    possel.verify_token().done(init).fail(do_login);
  }else{
    do_login();
  }
});
