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

/**
 * Deploy a feed to Bluesky and store metadata in DynamoDB
 */
const deployFeed = async (deployData) => {
  const {
    did,
    feedId,
    feedName,
    feedDescription,
    tunings,
    prompt,
    handle,
    password,
    access_jwt,
  } = deployData;

  // Validate required fields
  if (!did || !feedId || !feedName || !handle || !password) {
    return util.buildResponse(400, {
      message:
        "Missing required fields: did, feedId, feedName, handle, password",
    });
  }

  if (!Array.isArray(tunings)) {
    return util.buildResponse(400, { message: "Tunings must be an array" });
  }

  try {
    console.log(`[deployFeed] Starting deployment for ${did}/${feedId}`);

    // Convert tunings to blueprint format
    const blueprint = convertTuningsToBlueprint(
      tunings,
      feedName,
      feedDescription,
      prompt,
    );

    console.log(
      `[deployFeed] Blueprint created:`,
      JSON.stringify(blueprint, null, 2),
    );

    // Call feed-manager API to deploy the feed
    const feedManagerUrl =
      process.env.FEED_MANAGER_URL ||
      "https://papillon-feed-manager-ftzwl3vpfq-uc.a.run.app/manage-feed";

    const feedManagerPayload = {
      handle,
      password,
      hostname: `papillon-feed-manager-ftzwl3vpfq-uc.a.run.app/xrpc/app.bsky.feed.getFeedSkeleton`,
      blueprint,
      access_jwt,
    };

    console.log(`[deployFeed] Calling feed-manager at ${feedManagerUrl}`);

    const axios = require("axios");
    const feedManagerResponse = await axios.post(
      feedManagerUrl,
      feedManagerPayload,
      {
        headers: {
          "x-api-key": process.env.PAPILLON_API_KEY || "",
          "Content-Type": "application/json",
        },
      },
    );

    const feedUri = feedManagerResponse.data.uri;
    console.log(`[deployFeed] Feed deployed successfully: ${feedUri}`);

    // Store feed metadata in DynamoDB
    const now = new Date().toISOString();
    const params = {
      TableName: feedsTable,
      Key: { did },
      UpdateExpression:
        "SET feeds = if_not_exists(feeds, :emptyMap), feeds.#feedId = :feedData, updatedAt = :updatedAt",
      ExpressionAttributeNames: {
        "#feedId": feedId,
      },
      ExpressionAttributeValues: {
        ":emptyMap": {},
        ":feedData": {
          id: feedId,
          name: feedName,
          description: feedDescription || "",
          uri: feedUri,
          ruleset: blueprint,
          cache: [],
          createdAt: now,
          updatedAt: now,
        },
        ":updatedAt": now,
      },
      ReturnValues: "ALL_NEW",
    };

    const updateResult = await dynamodb.update(params).promise();
    console.log(`[deployFeed] Feed metadata stored in DynamoDB`);

    return util.buildResponse(200, {
      message: "Feed deployed successfully",
      uri: feedUri,
      feed: updateResult.Attributes.feeds[feedId],
    });
  } catch (error) {
    console.error("[deployFeed] Error:", error);
    const errorMessage =
      error.response?.data?.detail || error.message || "Failed to deploy feed";
    return util.buildResponse(500, {
      message: "Error deploying feed",
      error: errorMessage,
    });
  }
};

/**
 * Convert tunings array to blueprint format for feed-manager
 */
function convertTuningsToBlueprint(tunings, feedName, feedDescription, prompt) {
  const blueprint = {
    record_name: feedName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, ""),
    display_name: feedName,
    description: feedDescription || "",
    prompt: prompt || "",
    topic_preferences: [],
    profile_preferences: [],
    topic_filters: [],
    profile_filters: [],
    ranking_weights: {
      relevance: 0.5,
      popularity: 0.3,
      recency: 0.2,
    },
  };

  // Process tunings
  for (const tuning of tunings) {
    const weight = Math.abs(tuning.value) / 100; // Convert 0-100 to 0-1
    const isPositive = tuning.value >= 0;

    if (tuning.type === "topic") {
      if (isPositive) {
        blueprint.topic_preferences.push({
          name: tuning.label,
          weight,
        });
      } else {
        blueprint.topic_filters.push({
          name: tuning.label,
          weight,
        });
      }
    } else if (tuning.type === "account") {
      if (isPositive) {
        blueprint.profile_preferences.push({
          did: tuning.label,
          weight,
        });
      } else {
        blueprint.profile_filters.push({
          did: tuning.label,
          weight,
        });
      }
    }
  }

  return blueprint;
}

module.exports = {
  getFeeds,
  getFeed,
  updateRuleset,
  updateCache,
  initializeUser,
  deployFeed,
};
