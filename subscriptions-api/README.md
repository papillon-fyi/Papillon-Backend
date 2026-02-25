# Papillon Subscriptions API

AWS Lambda API for managing Papillon subscription tiers with Stripe integration.

## Database Structure

**Table**: `papillon-subscriptions`

**Primary Key**: `did` (String)

**Attributes**:

- `did`: User's Decentralized Identifier
- `tier`: Subscription tier (`"free"`, `"pro"`, or `"max"`)
- `stripeCustomerId`: Stripe customer ID (if paid tier)
- `stripeSubscriptionId`: Stripe subscription ID (if paid tier)
- `createdAt`: ISO timestamp
- `updatedAt`: ISO timestamp

## Subscription Tiers

### Free

- **Max Feeds**: 1
- **Customization**: No
- **Ads**: Yes
- **Price**: Free

### Pro

- **Max Feeds**: 5
- **Customization**: Yes
- **Ads**: No
- **Price**: Set via Stripe

### Max

- **Max Feeds**: Unlimited
- **Customization**: Yes
- **Ads**: No
- **Price**: Set via Stripe

## API Endpoints

### Health Check

- `GET /health` - Returns health status

### Subscriptions

- `GET /subscriptions/{did}` - Get subscription for a DID
  - Returns subscription tier and capabilities (maxFeeds, customization, ads)
  - Returns default "free" if no subscription exists

- `POST /subscriptions/{did}/upgrade` - Upgrade subscription

  ```json
  {
    "targetTier": "pro" or "max",
    "paymentMethodId": "pm_123..."
  }
  ```

  - Validates upgrade path (free → pro → max)
  - Creates Stripe subscription
  - Updates DynamoDB

- `POST /subscriptions/{did}/downgrade` - Downgrade subscription

  ```json
  {
    "targetTier": "free" or "pro"
  }
  ```

  - Validates downgrade path (max → pro → free)
  - Cancels Stripe subscription if downgrading to free
  - Updates DynamoDB

## Environment Variables

Required:

- `STRIPE_SECRET_KEY` - Stripe API secret key
- `STRIPE_PRO_PRICE_ID` - Stripe Price ID for Pro tier
- `STRIPE_MAX_PRICE_ID` - Stripe Price ID for Max tier

## Stripe Integration

The Stripe integration includes stub functions ready to be implemented:

### `createStripeCheckoutSession(did, tier, paymentMethodId)`

Creates a Stripe customer and subscription for the user.

**TODO**: Implement actual Stripe API calls:

```javascript
const customer = await stripe.customers.create({ metadata: { did } });
const subscription = await stripe.subscriptions.create({
  customer: customer.id,
  items: [{ price: SUBSCRIPTION_TIERS[tier].priceId }],
  default_payment_method: paymentMethodId,
});
```

### `cancelStripeSubscription(subscriptionId)`

Cancels a Stripe subscription when downgrading to free.

**TODO**: Implement actual Stripe API call:

```javascript
await stripe.subscriptions.cancel(subscriptionId);
```

## Frontend Usage

The frontend can check subscription capabilities to determine what features to enable:

```javascript
const response = await fetch(`/subscriptions/${userDid}`);
const { subscription, maxFeeds, customization, ads } = await response.json();

// Enable/disable features based on subscription
if (maxFeeds === -1 || userFeeds.length < maxFeeds) {
  enableCreateFeed();
}
if (customization) {
  enableFeedCustomization();
}
if (ads) {
  showAdvertisements();
}
```

## Deployment

1. Install dependencies: `npm install`
2. Set environment variables for Stripe keys and price IDs
3. Deploy via AWS Lambda
4. Create `papillon-subscriptions` DynamoDB table with `did` as primary key
5. Ensure Lambda has DynamoDB and Stripe API access
