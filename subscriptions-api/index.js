const subscriptionsService = require("./services/subscriptions");
const util = require("./utils/util");

const healthPath = "/health";
const subscriptionsPath = "/subscriptions";

exports.handler = async (event) => {
  let response;
  switch (true) {
    case event.httpMethod === "GET" && event.path === healthPath:
      response = util.buildResponse(200, { status: "healthy" });
      break;

    // Get subscription for a DID
    case event.httpMethod === "GET" &&
      event.path.match(/^\/subscriptions\/[^/]+$/):
      const did = event.path.slice(subscriptionsPath.length + 1);
      response = await subscriptionsService.getSubscription(did);
      break;

    // Upgrade subscription
    case event.httpMethod === "POST" &&
      event.path.match(/^\/subscriptions\/[^/]+\/upgrade$/):
      const upgradeDid = event.path
        .slice(subscriptionsPath.length + 1)
        .split("/")[0];
      const upgradeBody = JSON.parse(event.body);
      response = await subscriptionsService.upgrade(upgradeDid, upgradeBody);
      break;

    // Downgrade subscription
    case event.httpMethod === "POST" &&
      event.path.match(/^\/subscriptions\/[^/]+\/downgrade$/):
      const downgradeDid = event.path
        .slice(subscriptionsPath.length + 1)
        .split("/")[0];
      const downgradeBody = JSON.parse(event.body);
      response = await subscriptionsService.downgrade(
        downgradeDid,
        downgradeBody,
      );
      break;

    default:
      response = util.buildResponse(404, { message: "404 not found" });
  }
  return response;
};
