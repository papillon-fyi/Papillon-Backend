const feedsService = require("./services/feeds");
const util = require("./utils/util");

const healthPath = "/health";
const feedsPath = "/feeds";

exports.handler = async (event) => {
  let response;

  const method = event.httpMethod;

  // Use proxy path when available (REST API with /{proxy+})
  const path = event.pathParameters?.proxy
    ? "/" + event.pathParameters.proxy
    : event.path;

  // Handle CORS preflight OPTIONS requests
  if (method === "OPTIONS") {
    return util.buildResponse(200, {});
  }

  switch (true) {
    case method === "GET" && path === healthPath:
      response = util.buildResponse(200, { status: "healthy" });
      break;

    // GET /feeds/{did}
    case method === "GET" && /^\/feeds\/[^/]+$/.test(path): {
      const accountDid = path.slice(feedsPath.length + 1);
      response = await feedsService.getFeeds(accountDid);
      break;
    }

    // GET /feeds/{did}/{feedId}
    case method === "GET" && /^\/feeds\/[^/]+\/[^/]+$/.test(path): {
      const parts = path.slice(feedsPath.length + 1).split("/");
      response = await feedsService.getFeed(parts[0], parts[1]);
      break;
    }

    // POST /feeds/{did}/{feedId}/ruleset
    case method === "POST" && /^\/feeds\/[^/]+\/[^/]+\/ruleset$/.test(path): {
      const parts = path.slice(feedsPath.length + 1).split("/");
      const body = JSON.parse(event.body || "{}");
      response = await feedsService.updateRuleset(parts[0], parts[1], body);
      break;
    }

    // POST /feeds/{did}/{feedId}/cache
    case method === "POST" && /^\/feeds\/[^/]+\/[^/]+\/cache$/.test(path): {
      const parts = path.slice(feedsPath.length + 1).split("/");
      const body = JSON.parse(event.body || "{}");
      response = await feedsService.updateCache(parts[0], parts[1], body);
      break;
    }

    // POST /feeds/{did}/initialize
    case method === "POST" && /^\/feeds\/[^/]+\/initialize$/.test(path): {
      const parts = path.slice(feedsPath.length + 1).split("/");
      response = await feedsService.initializeUser(parts[0]);
      break;
    }

    default:
      response = util.buildResponse(404, { message: "404 not found" });
  }

  return response;
};
