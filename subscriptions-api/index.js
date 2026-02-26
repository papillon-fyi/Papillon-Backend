const subscriptionsService = require("./services/subscriptions");
const util = require("./utils/util");

const healthPath = "/health";
const subscriptionsPath = "/subscriptions";

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

    // GET /subscriptions/{did}
    case method === "GET" && /^\/subscriptions\/[^/]+$/.test(path): {
      const did = path.slice(subscriptionsPath.length + 1);
      response = await subscriptionsService.getSubscription(did);
      break;
    }

    // POST /subscriptions/{did}/upgrade
    case method === "POST" && /^\/subscriptions\/[^/]+\/upgrade$/.test(path): {
      const parts = path.slice(subscriptionsPath.length + 1).split("/");
      const body = JSON.parse(event.body || "{}");
      response = await subscriptionsService.upgrade(parts[0], body);
      break;
    }

    // POST /subscriptions/{did}/downgrade
    case method === "POST" &&
      /^\/subscriptions\/[^/]+\/downgrade$/.test(path): {
      const parts = path.slice(subscriptionsPath.length + 1).split("/");
      const body = JSON.parse(event.body || "{}");
      response = await subscriptionsService.downgrade(parts[0], body);
      break;
    }

    default:
      response = util.buildResponse(404, { message: "404 not found" });
  }

  return response;
};
