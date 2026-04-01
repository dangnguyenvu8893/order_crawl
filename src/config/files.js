const fs = require("node:fs");
const path = require("node:path");

const ROOT_DIR = path.resolve(__dirname, "../..");
const CONFIG_DIRS = [
  path.join(ROOT_DIR, "config"),
  path.join(ROOT_DIR, "crawl_new", "config")
];

function getConfigSearchPaths(filename) {
  return CONFIG_DIRS.map((directory) => path.join(directory, filename));
}

function loadOptionalJsonFile(filename) {
  const candidatePaths = getConfigSearchPaths(filename);

  for (const filePath of candidatePaths) {
    try {
      return {
        path: filePath,
        data: JSON.parse(fs.readFileSync(filePath, "utf8"))
      };
    } catch (error) {
      if (error.code === "ENOENT") {
        continue;
      }

      throw error;
    }
  }

  return {
    path: candidatePaths[0],
    data: {}
  };
}

module.exports = {
  CONFIG_DIRS,
  ROOT_DIR,
  getConfigSearchPaths,
  loadOptionalJsonFile
};
