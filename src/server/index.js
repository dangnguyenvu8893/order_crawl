const { SERVICE_PORT } = require("../config");
const { createServer } = require("./app");

function startServer({ port = SERVICE_PORT } = {}) {
  const server = createServer();
  server.listen(port, () => {
    process.stdout.write(`Crawler service listening on port ${port}\n`);
  });
  return server;
}

if (require.main === module) {
  startServer();
}

module.exports = {
  startServer
};
