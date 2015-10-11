"use strict";

var possel = {
  users: [],
  buffers: [],
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
    return $.get("/line?last=1");
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

var PosselTemplate = {
  templates: {},
  orange: '#C9952E',
  load: function(url){
    var that = this;
    return $.get(url, function(html, textStatus, jqXhr){
      var obj = $('<div/>').html(html).contents().filter('div');
      obj.each(function(index, template){
        that.templates[template.id] = Handlebars.compile(template.innerHTML);
      });
    });
  },
}

$(function(){
  var users = [], buffers = [];


  function scroll_to_bottom(element){
    element.scrollTop(element.prop('scrollHeight'));
  }

  function new_user(user){
    users[user.id] = user;
    user.color = Please.make_color();
  }

  function prepopulate_line_buffer(line_id, buffer_id){
    $('#' + buffer_id).append(PosselTemplate.templates.prepopulate_line({line_id: line_id}));
  }

  function new_line(line){
    var buffer = buffers[line.buffer], user = users[line.user], use_user, line_element;
    use_user = user;
    if(user == null){
      use_user = {
        color: PosselTemplate.orange,
      }
    }
    switch(line.kind){
      case 'action':
      case 'join':
      case 'quit':
      case 'part':
        use_user = {
          color: PosselTemplate.orange,
        };
        line.content = line.nick + ' ' + line.content;
        line.nick = '-*-';
        break;
    }

    line_element = $('#line-' + line.id);
    line_element.addClass('buffer-line-' + line.kind);

    line_element.append(PosselTemplate.templates.line({
      line: line,
      user: use_user,
      timestamp: moment.unix(line.timestamp).format('HH:mm:ss'),
    }));

    // Do some colouring
    switch(line.kind){
      case 'action':
        line_element.attr('style', 'color: ' + user.color + ';');
        break;
      case 'notice':
        line_element.attr('style', 'color: ' + PosselTemplate.orange + ';');
        break;
      case 'join':
      case 'part':
      case 'quit':
        line_element.attr('style', 'color: gray;');
        break;
    }
    line_element.linkify({target: '_blank'});
    scroll_to_bottom($('#message-pane'));
  }

  function new_buffer(buffer){
      var buffer_link, nav_item = PosselTemplate.templates.nav_item;
      buffers[buffer.id] = buffer;
      switch(buffer.kind){
        case "system":
          $('#bufferlist').append(nav_item({
            buffer: buffer,
            system: true,
          }));
          break;
        case "normal":
          $('#server-buffer-link-' + buffer.server).after(nav_item({
            buffer: buffer,
            system: false,
          }));
          break;
      }
      $("#message-pane").append(PosselTemplate.templates.buffer_pane({buffer: buffer}));
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
        prepopulate_line_buffer(line.id, line.buffer);
        new_line(line);
      });
    });
  }

  function handle_push(event){
    var msg = JSON.parse(event.data);
    switch(msg.type){
    case "line":
      prepopulate_line_buffer(msg.line, msg.buffer);
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
        new_user(user_data[0]);
      });
    }
  }

  function init(){
    console.log('Initializing');
    possel.events.submit_event('#message-input-form');
    $(document).keypress(function(e){
      $('#message-input').focus();
    });
    $.when(possel.get_user("all"),
        possel.get_buffer("all"),
        possel.get_last_line(),
        PosselTemplate.load('/static/templates.html')
        )
      .done(function(user_data, buffer_data, last_line_data){
        console.log('done preparing');
        user_data[0].forEach(function(user){
          new_user(user);
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
