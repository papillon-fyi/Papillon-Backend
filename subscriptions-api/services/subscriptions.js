const AWS = require("aws-sdk");
const stripe = require("stripe")(process.env.STRIPE_SECRET_KEY);
AWS.config.update({
  region: "us-east-1",
});
const util = require("../utils/util");
const dynamodb = new AWS.DynamoDB.DocumentClient();
const subscriptionsTable = "papillon-subscriptions";

// Subscription tier pricing (Stripe Price IDs - set these in environment variables)
const SUBSCRIPTION_TIERS = {
  free: {
    name: "Free",
    maxFeeds: 1,
    customization: false,
    ads: true,
    priceId: null, // Free tier has no Stripe price
  },
  pro: {
    name: "Pro",
    maxFeeds: 5,
    customization: true,
    ads: false,
    priceId: process.env.STRIPE_PRO_PRICE_ID,
  },
  max: {
    name: "Max",
    maxFeeds: -1, // unlimited
    customization: true,
    ads: false,
    priceId: process.env.STRIPE_MAX_PRICE_ID,
  },
};

/**
 * Get subscription for a DID
 */
const getSubscription = async (did) => {
  if (!did) {
    return util.buildResponse(400, { message: "DID is required" });
  }

  const params = {
    TableName: subscriptionsTable,
    Key: { did },
  };

  return await dynamodb
    .get(params)
    .promise()
    .then(
      (response) => {
        if (!response.Item) {
          // Return default free subscription if not found
          return util.buildResponse(200, {
            did: did,
            subscription: "free",
            ...SUBSCRIPTION_TIERS.free,
          });
        }
        return util.buildResponse(200, {
          ...response.Item,
          ...SUBSCRIPTION_TIERS[response.Item.subscription],
        });
      },
      (error) => {
        console.error("Error getting subscription: ", error);
        return util.buildResponse(500, {
          message: "Error getting subscription",
        });
      },
    );
};

/**
 * Upgrade subscription using Stripe
 */
const upgrade = async (did, upgradeInfo) => {
  if (!did) {
    return util.buildResponse(400, { message: "DID is required" });
  }

  const { targetTier, paymentMethodId } = upgradeInfo;

  // Validate target tier
  if (!["pro", "max"].includes(targetTier)) {
    return util.buildResponse(400, {
      message: "Invalid target tier. Must be 'pro' or 'max'",
    });
  }

  // Get current subscription
  const currentSub = await dynamodb
    .get({
      TableName: subscriptionsTable,
      Key: { did },
    })
    .promise();

  const currentTier = currentSub.Item?.subscription || "free";

  // Validate upgrade path
  const tierOrder = ["free", "pro", "max"];
  if (tierOrder.indexOf(targetTier) <= tierOrder.indexOf(currentTier)) {
    return util.buildResponse(400, {
      message: `Cannot upgrade from ${currentTier} to ${targetTier}`,
    });
  }

  try {
    // Create Stripe checkout session or subscription
    // TODO: Implement actual Stripe payment flow
    // For now, this is a stub that would integrate with Stripe
    const stripeSession = await createStripeCheckoutSession(
      did,
      targetTier,
      paymentMethodId,
    );

    // Update subscription in DynamoDB
    const params = {
      TableName: subscriptionsTable,
      Key: { did },
      UpdateExpression:
        "SET subscription = :tier, stripeCustomerId = :customerId, stripeSubscriptionId = :subscriptionId, updatedAt = :updatedAt",
      ExpressionAttributeValues: {
        ":tier": targetTier,
        ":customerId": stripeSession.customerId,
        ":subscriptionId": stripeSession.subscriptionId,
        ":updatedAt": new Date().toISOString(),
      },
      ReturnValues: "ALL_NEW",
    };

    return await dynamodb
      .update(params)
      .promise()
      .then(
        (response) => {
          return util.buildResponse(200, {
            message: `Successfully upgraded to ${targetTier}`,
            subscription: response.Attributes,
            ...SUBSCRIPTION_TIERS[targetTier],
          });
        },
        (error) => {
          console.error("Error upgrading subscription: ", error);
          return util.buildResponse(500, {
            message: "Error upgrading subscription",
          });
        },
      );
  } catch (error) {
    console.error("Stripe error: ", error);
    return util.buildResponse(500, { message: "Payment processing failed" });
  }
};

/**
 * Downgrade subscription
 */
const downgrade = async (did, downgradeInfo) => {
  if (!did) {
    return util.buildResponse(400, { message: "DID is required" });
  }

  const { targetTier } = downgradeInfo;

  // Validate target tier
  if (!["free", "pro"].includes(targetTier)) {
    return util.buildResponse(400, {
      message: "Invalid target tier. Must be 'free' or 'pro'",
    });
  }

  // Get current subscription
  const currentSub = await dynamodb
    .get({
      TableName: subscriptionsTable,
      Key: { did },
    })
    .promise();

  const currentTier = currentSub.Item?.subscription || "free";

  // Validate downgrade path
  const tierOrder = ["free", "pro", "max"];
  if (tierOrder.indexOf(targetTier) >= tierOrder.indexOf(currentTier)) {
    return util.buildResponse(400, {
      message: `Cannot downgrade from ${currentTier} to ${targetTier}`,
    });
  }

  try {
    // Cancel Stripe subscription if downgrading to free
    if (targetTier === "free" && currentSub.Item?.stripeSubscriptionId) {
      await cancelStripeSubscription(currentSub.Item.stripeSubscriptionId);
    }

    // Update subscription in DynamoDB
    const params = {
      TableName: subscriptionsTable,
      Key: { did },
      UpdateExpression: "SET subscription = :tier, updatedAt = :updatedAt",
      ExpressionAttributeValues: {
        ":tier": targetTier,
        ":updatedAt": new Date().toISOString(),
      },
      ReturnValues: "ALL_NEW",
    };

    return await dynamodb
      .update(params)
      .promise()
      .then(
        (response) => {
          return util.buildResponse(200, {
            message: `Successfully downgraded to ${targetTier}`,
            subscription: response.Attributes,
            ...SUBSCRIPTION_TIERS[targetTier],
          });
        },
        (error) => {
          console.error("Error downgrading subscription: ", error);
          return util.buildResponse(500, {
            message: "Error downgrading subscription",
          });
        },
      );
  } catch (error) {
    console.error("Error cancelling Stripe subscription: ", error);
    return util.buildResponse(500, {
      message: "Error downgrading subscription",
    });
  }
};

/**
 * STRIPE INTEGRATION STUBS
 * TODO: Implement actual Stripe API calls
 */

async function createStripeCheckoutSession(did, tier, paymentMethodId) {
  // TODO: Implement Stripe checkout session creation
  // Example:
  // const customer = await stripe.customers.create({ metadata: { did } });
  // const subscription = await stripe.subscriptions.create({
  //   customer: customer.id,
  //   items: [{ price: SUBSCRIPTION_TIERS[tier].priceId }],
  //   payment_behavior: 'default_incomplete',
  //   default_payment_method: paymentMethodId,
  // });
  // return { customerId: customer.id, subscriptionId: subscription.id };

  // Stub implementation
  return {
    customerId: `cus_stub_${did}`,
    subscriptionId: `sub_stub_${did}_${tier}`,
  };
}

async function cancelStripeSubscription(subscriptionId) {
  // TODO: Implement Stripe subscription cancellation
  // Example:
  // await stripe.subscriptions.cancel(subscriptionId);

  // Stub implementation
  console.log(`[STUB] Cancelling Stripe subscription: ${subscriptionId}`);
  return true;
}

module.exports = {
  getSubscription,
  upgrade,
  downgrade,
};
