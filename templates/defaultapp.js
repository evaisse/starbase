
var http = require('http'),
    server;


//We need a function which handles requests and send response
function handleRequest(request, response){
    response.end('It Works !');
}

//Create a server
server = http.createServer(handleRequest);

//Lets start our server
server.listen(process.env.PORT || 3000, function() {
    //Callback triggered when server is successfully listening. Hurray!
    console.log("Server listening on: http://localhost:%s", process.env.PORT);
});