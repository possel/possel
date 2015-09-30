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

$(function(){
    var users = [], buffers = [];

    function new_line(line){
        var buffer = buffers[line.buffer], user = users[line.user];
        $("body").append("<div><span>" + buffer.name + "</span><span>" + user.nick + "</span><span>" + line.content + "</span>");
    }

    function prepopulate_lines(last_line_data, nlines){
        var last_line = last_line_data[0];
        $.get("/line?after=" + (last_line.id - nlines)).then(function(lines){
            lines.forEach(function(line){
                new_line(line);
            });
        });
    }

    function handle_push(evt){
        var id = evt.data;
        get_line_by_id(id).then(function(data) {
            var line = data[0];
            new_line(line);
        });
    }

    $.when(get_user("all"),
          get_buffer("all"),
          get_last_line()
         )
        .done(function(user_data, buffer_data, last_line_data){
            user_data[0].forEach(function(user){
                users[user.id] = user;
            });
            buffer_data[0].forEach(function(buffer) {
                buffers[buffer.id] = buffer;
            });
            var ws = new WebSocket(ws_url);
            ws.onopen = function() {
                console.log("connected");
            };
            ws.onmessage = handle_push;
            prepopulate_lines(last_line_data[0], 30);
        });
});
