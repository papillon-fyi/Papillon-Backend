const AWS = require("aws-sdk");
AWS.config.update({
  region: "us-east-1",
});
const util = require("../utils/util");
const dynamodb = new AWS.DynamoDB.DocumentClient();
const feedsTable = "papillon-feeds";
const subscriptionsTable = "papillon-subscriptions";

/**
 * Get all feeds for an account
 */
const getFeeds = async (did) => {
  if (!did) {
    return util.buildResponse(400, { message: "DID is required" });
  }

  const params = {
    TableName: feedsTable,
    Key: { did },
  };

  return await dynamodb
    .get(params)
    .promise()
    .then(
      (response) => {
        if (!response.Item) {
          return util.buildResponse(404, { message: "Account not found" });
        }
        return util.buildResponse(200, response.Item.feeds || {});
      },
      (error) => {
        console.error("Error getting feeds: ", error);
        return util.buildResponse(500, { message: "Error getting feeds" });
      },
    );
};

/**
 * Get specific feed for an account
 */
const getFeed = async (did, feedId) => {
  if (!did || !feedId) {
    return util.buildResponse(400, { message: "DID and feedId are required" });
  }

  const params = {
    TableName: feedsTable,
    Key: { did },
  };

  return await dynamodb
    .get(params)
    .promise()
    .then(
      (response) => {
        if (!response.Item) {
          return util.buildResponse(404, { message: "Account not found" });
        }
        const feed = response.Item.feeds?.[feedId];
        if (!feed) {
          return util.buildResponse(404, { message: "Feed not found" });
        }
        return util.buildResponse(200, feed);
      },
      (error) => {
        console.error("Error getting feed: ", error);
        return util.buildResponse(500, { message: "Error getting feed" });
      },
    );
};

/**
 * Update feed ruleset
 */
const updateRuleset = async (did, feedId, rulesetData) => {
  if (!did || !feedId) {
    return util.buildResponse(400, { message: "DID and feedId are required" });
  }

  if (!rulesetData.ruleset) {
    return util.buildResponse(400, { message: "Ruleset data is required" });
  }

  const params = {
    TableName: feedsTable,
    Key: { did },
    UpdateExpression:
      "SET feeds.#feedId.ruleset = :ruleset, updatedAt = :updatedAt",
    ExpressionAttributeNames: {
      "#feedId": feedId,
    },
    ExpressionAttributeValues: {
      ":ruleset": rulesetData.ruleset,
      ":updatedAt": new Date().toISOString(),
    },
    ReturnValues: "ALL_NEW",
  };

  return await dynamodb
    .update(params)
    .promise()
    .then(
      (response) => {
        return util.buildResponse(200, response.Attributes.feeds[feedId]);
      },
      (error) => {
        console.error("Error updating ruleset: ", error);
        return util.buildResponse(500, { message: "Error updating ruleset" });
      },
    );
};

/**
 * Update feed cache (array of post URIs)
 */
const updateCache = async (did, feedId, cacheData) => {
  if (!did || !feedId) {
    return util.buildResponse(400, { message: "DID and feedId are required" });
  }

  if (!Array.isArray(cacheData.cache)) {
    return util.buildResponse(400, {
      message: "Cache must be an array of post URIs",
    });
  }

  const params = {
    TableName: feedsTable,
    Key: { did },
    UpdateExpression:
      "SET feeds.#feedId.#cache = :cache, updatedAt = :updatedAt",
    ExpressionAttributeNames: {
      "#feedId": feedId,
      "#cache": "cache",
    },
    ExpressionAttributeValues: {
      ":cache": cacheData.cache,
      ":updatedAt": new Date().toISOString(),
    },
    ReturnValues: "ALL_NEW",
  };

  return await dynamodb
    .update(params)
    .promise()
    .then(
      (response) => {
        return util.buildResponse(200, response.Attributes.feeds[feedId]);
      },
      (error) => {
        console.error("Error updating cache: ", error);
        return util.buildResponse(500, { message: "Error updating cache" });
      },
    );
};

/**
 * Initialize a new user with a default feed and free subscription
 */
const initializeUser = async (did) => {
  if (!did) {
    return util.buildResponse(400, { message: "DID is required" });
  }

  // Check if user already exists
  const existingUser = await dynamodb
    .get({
      TableName: feedsTable,
      Key: { did },
    })
    .promise();

  if (existingUser.Item) {
    return util.buildResponse(409, {
      message: "User already exists",
      data: existingUser.Item,
    });
  }

  const now = new Date().toISOString();
  const defaultFeedId = "default";

  // Create account with default feed
  const accountParams = {
    TableName: feedsTable,
    Item: {
      did,
      feeds: {
        [defaultFeedId]: {
          id: defaultFeedId,
          name: "My Feed",
          ruleset: {
            topics: [],
            accounts: [],
            keywords: [],
          },
          cache: [],
          createdAt: now,
          updatedAt: now,
        },
      },
      createdAt: now,
      updatedAt: now,
    },
  };

  // Create free subscription
  const subscriptionParams = {
    TableName: subscriptionsTable,
    Item: {
      did,
      tier: "free",
      stripeCustomerId: null,
      stripeSubscriptionId: null,
      createdAt: now,
      updatedAt: now,
    },
  };

  try {
    // Write both items to DynamoDB
    await Promise.all([
      dynamodb.put(accountParams).promise(),
      dynamodb.put(subscriptionParams).promise(),
    ]);

    return util.buildResponse(201, {
      message: "User initialized successfully",
      account: accountParams.Item,
      subscription: subscriptionParams.Item,
    });
  } catch (error) {
    console.error("Error initializing user: ", error);
    return util.buildResponse(500, { message: "Error initializing user" });
  }
};

module.exports = {
  getFeeds,
  getFeed,
  updateRuleset,
  updateCache,
  initializeUser,
};
