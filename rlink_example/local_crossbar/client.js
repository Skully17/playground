
log_message = function (message) {
    console.log(`Recieved message: ${message}`);
}
call_local_1 = function () {
    connection._session.call("com.local.reg1", [message_to_send]);
}
call_local_2 = function () {
    connection._session.call("com.local.reg2", [message_to_send]);
}
call_remote_1 = function () {
    connection._session.call("com.remote.reg1", [message_to_send]);
}
call_remote_2 = function () {
    connection._session.call("com.remote.reg2", [message_to_send]);
}
call_local_js_1 = function () {
    connection._session.call("com.local.js.reg1", [message_to_send]);
}
call_local_js_2 = function () {
    connection._session.call("com.local.js.reg2", [message_to_send]);
}
call_remote_js_1 = function () {
    connection._session.call("com.remote.js.reg1", [message_to_send]);
}
call_remote_js_2 = function () {
    connection._session.call("com.remote.js.reg2", [message_to_send]);
}

let message_to_send = "local browser call";

let host = window.location.host;
let connection = new autobahn.Connection({
   url: `ws://${host}/ws`,
   realm: "realm1"
});
connection.onopen = function (session) {
    console.log("Connected to Crossbar");
    connection._session = session;

    session.register("com.local.js.reg1", log_message);
    session.register("com.local.js.reg2", log_message);
};
connection.open();
