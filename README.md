The Docker command you've executed is correctly mounting your local /Users/ethancheung/Downloads directory to the container directory /projects.

node dist/index.js /Users/ethancheung/Downloads


*** to run streamlit
streamlit run meta_frontend.py

run in terminal
npx -y @modelcontextprotocol/server-filesystem /Users/ethancheung/Downloads

*** github mcp server
https://github.com/aezizhu/simple-mcp-fileserver
npm install pdf-parse
npm install mammoth
npm install xlsx
npm install neo4j-driver


used to start the mcp server before you run the client
node simple-mcp-fileserver.js
