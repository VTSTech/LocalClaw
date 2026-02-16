---
name: web-search
description: Search the web for information, find current data, research topics, and retrieve web content. Use when the user needs current information, asks about recent events, or wants to search the internet.
license: MIT
metadata:
  author: VTSBot
  version: "1.0"
allowed-tools: Bash(curl:*) Bash(wget:*) Read Write
---

# Web Search Skill

This skill provides web search and content retrieval capabilities.

## When to Use This Skill

- User asks about current events or recent information
- User needs to search the internet
- User wants to retrieve web page content
- User asks "what is" questions about evolving topics
- User needs documentation or API references

## Capabilities

### Web Search

Search using various methods:

# Using duckduckgo HTML results
curl -s "https://html.duckduckgo.com/html/?q=SEARCH_TERM" | grep -oP 'class="result__a"[^>]*>[^<]*'
```

### Content Retrieval

Fetch web page content:

```bash
# Get raw HTML
curl -sL "https://example.com/page" > page.html

# Get with user agent
curl -sL -A "Mozilla/5.0" "https://example.com/page" > page.html

# Follow redirects and get final URL
curl -sLI "https://short.url" | grep -i "^location:"
```

### API Requests

Make API calls:

```bash
# GET request
curl -s "https://api.example.com/data" | jq .

# POST request with JSON
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}' \
  "https://api.example.com/endpoint" | jq .

# With authentication
curl -s -H "Authorization: Bearer TOKEN" "https://api.example.com/data"
```

## Step-by-Step Process

1. **Understand the information need**
   - What specific information does the user want?
   - Is it a simple fact or comprehensive research?

2. **Choose appropriate method**
   - Search engine for discovery
   - Direct URL for known sources
   - API for structured data

3. **Execute the search/fetch**
   ```bash
   # For search
   curl -s "SEARCH_URL?q=$(echo 'query' | jq -sRr @uri)"
   
   # For direct fetch
   curl -sL "https://target-site.com/page"
   ```

4. **Parse and extract relevant content**
   - Use grep, jq, or text processing
   - Extract key information
   - Summarize findings

5. **Present results to user**
   - Clear, organized summary
   - Cite sources
   - Provide relevant links

## Content Extraction

Extract text from HTML:

```bash
# Simple text extraction
curl -sL "https://example.com" | sed 's/<[^>]*>//g' | sed '/^\s*$/d'

# Extract specific elements (if lynx available)
lynx -dump "https://example.com"

# Extract links
curl -sL "https://example.com" | grep -oP 'href="[^"]*"' | cut -d'"' -f2
```

## Common Patterns

### Research a Topic

1. Search for overview articles
2. Fetch relevant pages
3. Extract key information
4. Synthesize findings

### Find Current Information

1. Search with date-relevant terms
2. Check multiple sources
3. Verify recency of information
4. Report with timestamps

### API Documentation Lookup

1. Identify API endpoint
2. Fetch documentation page
3. Extract relevant sections
4. Present to user

## Error Handling

```bash
# Check HTTP status
response=$(curl -sI "https://example.com" | head -1)
if echo "$response" | grep -q "200"; then
  echo "Success"
else
  echo "Failed: $response"
fi

# Handle timeouts
curl -sL --max-time 30 "https://example.com" || echo "Request timed out"

# Handle rate limits
curl -sL -H "Retry-After: 60" "https://api.example.com"
```

## Best Practices

- Always respect robots.txt and rate limits
- Use appropriate user agents
- Cache results when appropriate
- Validate URLs before fetching
- Handle encoding properly
