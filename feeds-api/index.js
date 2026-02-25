const feedsService = require("./services/feeds");
const util = require("./utils/util");

const healthPath = "/health";
const feedsPath = "/feeds";

exports.handler = async (event) => {
  let response;
  switch (true) {
    case event.httpMethod === "GET" && event.path === healthPath:
      response = util.buildResponse(200, { status: "healthy" });
      break;

    // Feed endpoints
    case event.httpMethod === "GET" && event.path.match(/^\/feeds\/[^/]+$/):
      // GET /feeds/{did} - get all feeds for an account
      const accountDid = event.path.slice(feedsPath.length + 1);
      response = await feedsService.getFeeds(accountDid);
      break;
    case event.httpMethod === "GET" &&
      event.path.match(/^\/feeds\/[^/]+\/[^/]+$/):
      // GET /feeds/{did}/{feedId} - get specific feed
      const parts = event.path.slice(feedsPath.length + 1).split("/");
      response = await feedsService.getFeed(parts[0], parts[1]);
      break;
    case event.httpMethod === "POST" &&
      event.path.match(/^\/feeds\/[^/]+\/[^/]+\/ruleset$/):
      // POST /feeds/{did}/{feedId}/ruleset - update feed ruleset
      const rulesetParts = event.path.slice(feedsPath.length + 1).split("/");
      const rulesetBody = JSON.parse(event.body);
      response = await feedsService.updateRuleset(
        rulesetParts[0],
        rulesetParts[1],
        rulesetBody,
      );
      break;
    case event.httpMethod === "POST" &&
      event.path.match(/^\/feeds\/[^/]+\/[^/]+\/cache$/):
      // POST /feeds/{did}/{feedId}/cache - update feed cache
      const cacheParts = event.path.slice(feedsPath.length + 1).split("/");
      const cacheBody = JSON.parse(event.body);
      response = await feedsService.updateCache(
        cacheParts[0],
        cacheParts[1],
        cacheBody,
      );
      break;
    case event.httpMethod === "POST" &&
      event.path.match(/^\/feeds\/[^/]+\/initialize$/):
      // POST /feeds/{did}/initialize - initialize new user with default feed and free subscription
      const initializeParts = event.path.slice(feedsPath.length + 1).split("/");
      response = await feedsService.initializeUser(initializeParts[0]);
      break;

    default:
      response = util.buildResponse(404, { message: "404 not found" });
  }
  return response;
};
