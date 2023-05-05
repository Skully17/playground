
log_message = function (message) {
    console.log(`Recieved message: ${message}`);
}
speak_to_alice = function () {
    connection._session.call("com.alice.speak", [hello]);
}
speak_to_charlie = function () {
    connection._session.call("com.charlie.speak", [hello]);
}
speak_to_bob = function () {
    connection._session.call("com.bob.speak", [hello]);
}

let hello = "Hello from Bob";

let host = window.location.host;
let connection = new autobahn.Connection({
   url: `ws://${host}/ws`,
   realm: "realm1"
});
connection.onopen = function (session) {
    console.log("Connected to Crossbar");
    connection._session = session;

    session.register("com.bob.speak", log_message);
    session.subscribe("com.everyone.speak", log_message);
};
connection.open();
