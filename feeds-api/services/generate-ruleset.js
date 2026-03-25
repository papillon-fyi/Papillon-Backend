const OpenAI = require("openai");

// Bluesky API endpoints
const BSKY_API_BASE = "https://public.api.bsky.app/xrpc";

let clientInstance = null;

/**
 * Get or initialize OpenAI client
 */
function getClient() {
  if (!clientInstance) {
    clientInstance = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    });
  }
  return clientInstance;
}

/**
 * Strip potential code fences from response
 */
function stripCodeFences(text) {
  const trimmed = text.trim();
  if (!trimmed.startsWith("```")) {
    return trimmed;
  }
  const lines = trimmed.split("\n");
  const endIndex =
    lines[lines.length - 1] === "```" ? lines.length - 1 : lines.length;
  return lines.slice(1, endIndex).join("\n").trim();
}

/**
 * Search for actors on Bluesky matching a query
 */
async function searchBlueskyActors(query, limit = 5) {
  const url = `${BSKY_API_BASE}/app.bsky.actor.searchActors`;
  const params = new URLSearchParams({
    q: query,
    limit: limit.toString(),
  });

  try {
    const response = await fetch(`${url}?${params}`, {
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      console.log(
        `[searchBlueskyActors] Search failed for "${query}": HTTP ${response.status}`,
      );
      return [];
    }

    const data = await response.json();
    const actors = data.actors || [];

    if (actors.length === 0) {
      console.log(`[searchBlueskyActors] No actors found for "${query}"`);
      return [];
    }

    console.log(
      `[searchBlueskyActors] Found ${actors.length} actors for "${query}"`,
    );

    // Return DIDs with weights (higher weight for top results)
    // Weight decreases from 1.0 for first result to 0.5 for 5th result
    return actors
      .map((actor, index) => ({
        did: actor.did,
        weight: 1.0 - index * 0.1, // 1.0, 0.9, 0.8, 0.7, 0.6
      }))
      .filter((item) => item.did);
  } catch (error) {
    console.log(
      `[searchBlueskyActors] Error searching for "${query}": ${error.message}`,
    );
    return [];
  }
}

/**
 * Search for suggested accounts across all topics
 */
async function getSuggestedAccounts(topicPreferences) {
  console.log("\n" + "=".repeat(60));
  console.log("FETCHING SUGGESTED ACCOUNTS FROM BLUESKY");
  console.log("=".repeat(60));

  const topicQueries = topicPreferences.map((t) => t.name);
  console.log(
    `[getSuggestedAccounts] Searching for accounts matching topics: ${topicQueries.join(", ")}\n`,
  );

  // Search for each topic in parallel, get top 5 accounts per topic
  const results = await Promise.all(
    topicQueries.map((topic) => searchBlueskyActors(topic, 5)),
  );

  // Collect all unique accounts with their best weight across topics
  const accountMap = new Map(); // did -> best weight
  for (const topicResults of results) {
    for (const { did, weight } of topicResults) {
      if (!accountMap.has(did) || weight > accountMap.get(did)) {
        accountMap.set(did, weight);
      }
    }
  }

  // Sort by weight (descending) and limit to top 10
  const allAccounts = Array.from(accountMap.entries())
    .map(([did, weight]) => ({ did, weight }))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 10);

  console.log(
    `[getSuggestedAccounts] Found ${accountMap.size} unique accounts, returning top ${allAccounts.length}\n`,
  );

  return allAccounts;
}

/**
 * Generate feed ruleset using OpenAI
 */
async function generateFeedRuleset(query) {
  console.log("[generateFeedRuleset] Starting generation...");
  console.log(`[generateFeedRuleset] Query: ${query.substring(0, 100)}...`);

  const client = getClient();

  const systemPrompt = `You are a Bluesky feed ruleset generator. Generate structured feed configurations based on user descriptions.

FEED RULESET STRUCTURE:

A feed ruleset defines how to curate and rank posts from Bluesky. Each ruleset contains:

1. METADATA:
   - record_name: filesystem-safe identifier (lowercase-with-hyphens, no spaces)
   - display_name: human-readable name (less than 5 words)
   - description: brief explanation of feed purpose (1-2 sentences)

2. TOPIC PREFERENCES (required):
   Array of topics the user wants to see. Each topic has:
   - name: 1-2 word topic/subject (keep to max 5 topics total)
   - weight: importance score between 0.3 and 1.0

3. TOPIC FILTERS (optional):
   Array of topics to avoid or limit. Each filter has:
   - name: topic to filter out
   - weight: filter strength (default 0.5)

4. RANKING WEIGHTS (required):
   Controls post ranking algorithm:
   - relevance: how well post matches topics (default 0.5)
   - popularity: engagement/likes weight (default 0.3)
   - recency: how recent the post is (default 0.2)
   CRITICAL: These three values MUST sum to exactly 1.0

RULES:
- topic_preferences should represent meaningful subjects, entities, themes, or interests
- Avoid generic action words unless thematic to primary interests
- topic_filters are for content user wants to avoid (NFTs, politics, etc.)
- Keep topics concise (1-2 words each, max 5 topics)
- record_name must be lowercase with hyphens only
- display_name should be catchy but descriptive (under 5 words)
- ranking_weights must sum to exactly 1.0

OUTPUT FORMAT:
Return a JSON object with this EXACT structure:
{
  "record_name": "lowercase-hyphenated-name",
  "display_name": "Human Readable Name",
  "description": "Brief description of what this feed shows",
  "topic_preferences": [
    { "name": "topic1", "weight": 0.8 },
    { "name": "topic2", "weight": 0.7 }
  ],
  "topic_filters": [
    { "name": "unwanted", "weight": 0.5 }
  ],
  "ranking_weights": {
    "relevance": 0.5,
    "popularity": 0.3,
    "recency": 0.2
  }
}

Generate the JSON response now. NO markdown, NO code fences, ONLY the JSON object.`;

  const userPrompt = `Generate a feed ruleset for: "${query}"`;

  try {
    console.log("[generateFeedRuleset] Calling OpenAI...");
    const response = await client.chat.completions.create({
      model: "gpt-5-nano",
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
      response_format: { type: "json_object" },
      reasoning_effort: "minimal",
    });

    console.log("[generateFeedRuleset] OpenAI response received");

    // Parse the structured JSON response
    let rawResponse = response.choices[0].message.content || "{}";
    console.log(
      `[generateFeedRuleset] Raw response length: ${rawResponse.length} chars`,
    );

    // Strip potential code fences around JSON
    rawResponse = stripCodeFences(rawResponse);

    let feedFields;
    try {
      feedFields = JSON.parse(rawResponse);
    } catch (parseError) {
      console.error(
        "[generateFeedRuleset] JSON parse error:",
        parseError.message,
      );
      throw new Error("OpenAI returned invalid JSON: " + parseError.message);
    }

    // Add metadata
    feedFields.original_prompt = query;
    feedFields.generated_at = new Date().toISOString();

    // Normalize ranking_weights to ensure they sum to exactly 1.0
    if (feedFields.ranking_weights) {
      const weights = feedFields.ranking_weights;
      const total =
        (weights.relevance || 0.5) +
        (weights.popularity || 0.3) +
        (weights.recency || 0.2);

      if (total > 0) {
        weights.relevance = (weights.relevance || 0.5) / total;
        weights.popularity = (weights.popularity || 0.3) / total;
        weights.recency = (weights.recency || 0.2) / total;
      }
    } else {
      feedFields.ranking_weights = {
        relevance: 0.5,
        popularity: 0.3,
        recency: 0.2,
      };
    }

    // Fetch suggested accounts from Bluesky based on topic preferences
    if (
      feedFields.topic_preferences &&
      feedFields.topic_preferences.length > 0
    ) {
      const suggestedAccounts = await getSuggestedAccounts(
        feedFields.topic_preferences,
      );

      if (suggestedAccounts.length > 0) {
        feedFields.profile_preferences = suggestedAccounts;
        console.log(
          `[generateFeedRuleset] Added ${suggestedAccounts.length} profile preferences with variable weights`,
        );
      }
    }

    // Remove name/description from blueprint (they go at top level)
    const blueprint = { ...feedFields };
    delete blueprint.record_name;
    delete blueprint.display_name;
    delete blueprint.description;

    // Final response structure
    const result = {
      record_name: feedFields.record_name,
      display_name: feedFields.display_name,
      description: feedFields.description,
      blueprint,
    };

    console.log(
      `[generateFeedRuleset] Successfully generated ruleset: ${result.display_name}`,
    );
    return result;
  } catch (error) {
    console.error("[generateFeedRuleset] Error:", error.message);
    throw error;
  }
}

module.exports = {
  generateFeedRuleset,
};
