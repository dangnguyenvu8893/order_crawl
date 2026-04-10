const { SERVICE_PORT } = require("../config");
const { createServer } = require("./app");
const logger = require("./logger");

function startServer({ port = SERVICE_PORT } = {}) {
  const server = createServer();
  server.listen(port, () => {
    logger.info("Crawler service started", { port });
  });
  return server;
}

if (require.main === module) {
  const server = startServer();

  process.on("unhandledRejection", (error) => {
    logger.error("Unhandled promise rejection", { error });
  });

  process.on("uncaughtException", (error) => {
    logger.error("Uncaught exception", { error });
    server.close(() => process.exit(1));
  });
}

module.exports = {
  startServer
};
