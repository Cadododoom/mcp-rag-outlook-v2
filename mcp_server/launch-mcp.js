const net = require('net');
const path = require('path');
const dotenv = require('dotenv');

// Load environment from local .env file
dotenv.config({ path: path.join(__dirname, '.env') });

const milvusAddress = process.env.MILVUS_ADDRESS || 'localhost:19530';
const [host, port] = milvusAddress.split(':');

console.error(`[Launcher] Skipping Milvus standalone connection test (running CPU-offloaded LanceDB)...`);
launch();

function launch() {
  const { spawn } = require('child_process');
  console.error('[Launcher] Spawning AST-aware code indexer MCP server...');

  // Setup environment for the child process
  const childEnv = {
    ...process.env,
    EMBEDDING_PROVIDER: process.env.EMBEDDING_PROVIDER || 'OpenAI',
    OPENAI_BASE_URL: process.env.OPENAI_BASE_URL || 'http://localhost:1234/v1',
    OPENAI_API_KEY: process.env.OPENAI_API_KEY || 'lm-studio',
    EMBEDDING_MODEL: process.env.EMBEDDING_MODEL || 'text-embedding-nomic-embed-text-v1.5@q8_0',
    MILVUS_ADDRESS: milvusAddress
  };

  // Run the command using npx with stdio: inherit to allow full standard I/O communication (required by MCP)
  const cmd = process.platform === 'win32' ? 'npx.cmd' : 'npx';
  const child = spawn(cmd, ['-y', '@code-indexer/mcp@latest'], {
    env: childEnv,
    stdio: 'inherit',
    shell: true
  });

  child.on('close', (code) => {
    console.error(`[Launcher] MCP server exited with code ${code}`);
    process.exit(code);
  });
}
