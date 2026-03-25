const feedsService = require("./services/feeds");
const generateRulesetService = require("./services/generate-ruleset");
const { buildResponse } = require("./utils/util");

const healthPath = "/health";
const feedsPath = "/feeds";
const generateRulesetPath = "/feeds/generate-ruleset";
const deployFeedPath = "/feeds/deploy";

exports.handler = async (event) => {
  // Handle OPTIONS preflight
  if (event.httpMethod === "OPTIONS") {
    return buildResponse(200, {});
  }

  // Get path and method
  const path = event.pathParameters?.proxy
    ? "/" + event.pathParameters.proxy
    : event.path;
  const method = event.httpMethod;

  let response;

  switch (true) {
    case method === "GET" && path === healthPath:
      response = buildResponse(200, { status: "healthy" });
      break;

    // POST /feeds/generate-ruleset
    case method === "POST" && path === generateRulesetPath: {
      try {
        const body = JSON.parse(event.body || "{}");
        if (!body.query) {
          return buildResponse(400, { error: "Query is required" });
        }
        const ruleset = await generateRulesetService.generateFeedRuleset(
          body.query,
        );
        response = buildResponse(200, ruleset);
      } catch (error) {
        console.error("Error generating ruleset:", error);
        response = buildResponse(500, { error: error.message });
      }
      break;
    }

    // POST /feeds/deploy
    case method === "POST" && path === deployFeedPath: {
      try {
        const body = JSON.parse(event.body || "{}");
        response = await feedsService.deployFeed(body);
      } catch (error) {
        console.error("Error deploying feed:", error);
        response = buildResponse(500, { error: error.message });
      }
      break;
    }

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
      response = buildResponse(404, { message: "404 not found" });
  }

  return response;
};
