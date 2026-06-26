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
    EMBEDDING_PROVIDER: 'OpenAI',
    OPENAI_BASE_URL: 'http://127.0.0.1:8080/v1',
    OPENAI_API_KEY: 'none',
    EMBEDDING_MODEL: 'nomic-embed-text-v1.5.Q8_0.gguf',
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
