const readline = require('readline');
const http = require('http');

const MILVUS_URL = 'http://localhost:18080';
const EMBEDDING_URL = 'http://localhost:8080/v1/embeddings';

console.error('[Memory MCP] Starting Memory Manager MCP Server...');

// Helper to send HTTP requests
function postJson(urlStr, data) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const body = JSON.stringify(data);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
      timeout: 5000,
    };

    const req = http.request(options, (res) => {
      let responseBody = '';
      res.on('data', (chunk) => {
        responseBody += chunk;
      });
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(responseBody));
          } catch (e) {
            resolve(responseBody);
          }
        } else {
          reject(new Error(`HTTP Error ${res.statusCode}: ${responseBody}`));
        }
      });
    });

    req.on('error', (err) => reject(err));
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('HTTP Timeout'));
    });
    req.write(body);
    req.end();
  });
}

// Ensure collection exists in Milvus
async function ensureCollection() {
  try {
    console.error('[Memory MCP] Checking Milvus collection "agent_memories"...');
    const list = await postJson(`${MILVUS_URL}/v2/vectordb/collections/list`, {});
    const collections = (list && list.data) || [];
    if (!collections.includes('agent_memories')) {
      console.error('[Memory MCP] Creating "agent_memories" collection...');
      await postJson(`${MILVUS_URL}/v2/vectordb/collections/create`, {
        collectionName: 'agent_memories',
        dimension: 768,
      });
      console.error('[Memory MCP] Collection "agent_memories" created successfully.');
    } else {
      console.error('[Memory MCP] Collection "agent_memories" verified active.');
    }
  } catch (err) {
    console.error('[Memory MCP] Warning: Milvus connection or setup failed:', err.message);
  }
}

// Generate embedding vector using llama.cpp container
async function getEmbedding(text) {
  try {
    const res = await postJson(EMBEDDING_URL, { input: text });
    if (res && res.data && res.data[0] && res.data[0].embedding) {
      return res.data[0].embedding;
    }
    throw new Error('Invalid embedding response structure');
  } catch (err) {
    console.error('[Memory MCP] Embedding failed:', err.message);
    throw err;
  }
}

// Initialize setup
ensureCollection();

// JSON-RPC input loop
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false,
});

rl.on('line', async (line) => {
  if (!line.trim()) return;
  try {
    const request = JSON.parse(line);
    if (!request.method) return;

    switch (request.method) {
      case 'initialize':
        sendResponse(request.id, {
          protocolVersion: '2024-11-05',
          capabilities: {
            tools: {},
          },
          serverInfo: {
            name: 'memory-manager-mcp',
            version: '1.0.0',
          },
        });
        break;

      case 'notifications/initialized':
        // No response needed for notifications
        break;

      case 'ping':
        sendResponse(request.id, {});
        break;

      case 'tools/list':
        sendResponse(request.id, {
          tools: [
            {
              name: 'store_chat_memory',
              description: 'Store a conversation summary or key milestone fact in the long-term memory database. Use this to persist context when conversation history is long or running details need to be saved.',
              inputSchema: {
                type: 'object',
                properties: {
                  conversationId: {
                    type: 'string',
                    description: 'Unique identifier for the active agent conversation',
                  },
                  summary: {
                    type: 'string',
                    description: 'Concise summary of the memory/decision to store',
                  },
                  details: {
                    type: 'string',
                    description: 'Extended details, code changes, or context associated with this memory',
                  },
                },
                required: ['conversationId', 'summary'],
              },
            },
            {
              name: 'retrieve_chat_memory',
              description: 'Retrieve relevant past conversation summaries and milestones semantically using a natural language query.',
              inputSchema: {
                type: 'object',
                properties: {
                  conversationId: {
                    type: 'string',
                    description: 'Unique identifier for the active agent conversation',
                  },
                  query: {
                    type: 'string',
                    description: 'Semantic search query to retrieve matches for',
                  },
                  limit: {
                    type: 'number',
                    description: 'Max results to return (default 5)',
                  },
                },
                required: ['conversationId', 'query'],
              },
            },
          ],
        });
        break;

      case 'tools/call':
        await handleToolCall(request);
        break;

      default:
        sendError(request.id, -32601, `Method not found: ${request.method}`);
    }
  } catch (err) {
    console.error('[Memory MCP] Failed to process line:', err.message);
  }
});

async function handleToolCall(request) {
  const { name, arguments: args } = request.params || {};
  const id = request.id;

  try {
    if (name === 'store_chat_memory') {
      const { conversationId, summary, details } = args || {};
      if (!conversationId || !summary) {
        return sendToolError(id, 'Missing required arguments: conversationId and summary');
      }

      console.error(`[Memory MCP] Storing memory for ${conversationId}: ${summary}`);
      const vector = await getEmbedding(summary);

      const insertResult = await postJson(`${MILVUS_URL}/v2/vectordb/entities/insert`, {
        collectionName: 'agent_memories',
        data: [
          {
            id: Math.floor(Math.random() * 9000000000) + 1000000000,
            vector,
            conversationId,
            summary,
            details: details || '',
            timestamp: Date.now(),
          },
        ],
      });

      if (insertResult && insertResult.code !== 0) {
        throw new Error(`Milvus Insert Error: ${insertResult.message}`);
      }

      sendToolResult(id, `Successfully stored memory in database for conversation ${conversationId}.`);
    } else if (name === 'retrieve_chat_memory') {
      const { conversationId, query, limit } = args || {};
      if (!conversationId || !query) {
        return sendToolError(id, 'Missing required arguments: conversationId and query');
      }

      console.error(`[Memory MCP] Searching memory for ${conversationId}: ${query}`);
      const vector = await getEmbedding(query);

      const searchResult = await postJson(`${MILVUS_URL}/v2/vectordb/entities/search`, {
        collectionName: 'agent_memories',
        data: [vector],
        filter: `conversationId == "${conversationId}"`,
        limit: limit || 5,
        outputFields: ['summary', 'details', 'timestamp'],
      });

      if (searchResult && searchResult.code !== 0) {
        throw new Error(`Milvus Search Error: ${searchResult.message}`);
      }

      const hits = (searchResult && searchResult.data) || [];
      if (hits.length === 0) {
        return sendToolResult(id, `No matching memories found for conversation ${conversationId}.`);
      }

      const formatted = hits.map((h, i) => {
        const time = new Date(h.timestamp).toISOString();
        return `[Memory ${i + 1}] (${time})\nSummary: ${h.summary}\nDetails: ${h.details}\n`;
      }).join('\n---\n\n');

      sendToolResult(id, formatted);
    } else {
      sendError(id, -32601, `Tool not found: ${name}`);
    }
  } catch (err) {
    console.error('[Memory MCP] Tool call execution error:', err.message);
    sendToolError(id, `Failed to execute tool: ${err.message}`);
  }
}

// Helper formatting outputs
function sendResponse(id, result) {
  console.log(JSON.stringify({
    jsonrpc: '2.0',
    id,
    result,
  }));
}

function sendError(id, code, message) {
  console.log(JSON.stringify({
    jsonrpc: '2.0',
    id,
    error: { code, message },
  }));
}

function sendToolResult(id, text) {
  sendResponse(id, {
    content: [
      {
        type: 'text',
        text,
      },
    ],
    isError: false,
  });
}

function sendToolError(id, message) {
  sendResponse(id, {
    content: [
      {
        type: 'text',
        text: `Error: ${message}`,
      },
    ],
    isError: true,
  });
}
