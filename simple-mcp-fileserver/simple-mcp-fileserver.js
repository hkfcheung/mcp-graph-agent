const neo4j = require('neo4j-driver');

const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env') });


console.log("🔐 Neo4j URI:", process.env.NEO4J_URI);
console.log("🔐 Neo4j USER:", process.env.NEO4J_USER);
console.log("🔐 Neo4j PASSWORD:", process.env.NEO4J_PASSWORD ? "set" : "NOT set");
console.log("CWD:", process.cwd());

const uri = process.env.NEO4J_URI;
const user = process.env.NEO4J_USER;
const password = process.env.NEO4J_PASSWORD;



const driver = neo4j.driver(
  "bolt://localhost:7687",
  neo4j.auth.basic("neo4j", "mySecurePass123")
);



async function saveToNeo4j(cypher, res, id) {
  const session = driver.session();
  try {
    // ❗ Remove BEGIN/COMMIT — not allowed in Aura
    // const cleanedCypher = cypher
    //   .replace(/\bBEGIN\b/g, '')
    //   .replace(/\bCOMMIT\b/g, '')
    //   .trim();
    
    console.log("📤 Sending Cypher:", cypher);

    const result = await session.run(cypher);
    console.log("✅ Neo4j Aura response:", result.summary);
    res.json({ jsonrpc: '2.0', result: { summary: result.summary }, id });
  } catch (err) {
    console.error("❌ Error saving to Neo4j:", err);
    res.json({ jsonrpc: '2.0', error: { code: 500, message: err.message }, id });
  } finally {
    await session.close();
  }
}

const express = require('express');
const fs = require('fs');
const app = express();

// Enable CORS for all routes
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

app.use(express.json());

// The MCP protocol uses JSON-RPC 2.0 format
app.post('/mcp', (req, res) => {
  console.log('Received MCP request:', JSON.stringify(req.body));
  res.setHeader('Content-Type', 'application/json');
  const { method, params, id } = req.body;
  if (method === 'initialize') {
    const response = {
      jsonrpc: '2.0',
      result: {
        capabilities: {
          readFile: { supported: true, description: 'Read a file from disk' },
          writeFile: { supported: true, description: 'Write a file to disk' },
          listDir: { supported: true, description: 'List directory contents' },
          get_weather: { supported: true, description: 'Get the current weather conditions for a location' },
          saveToNeo4j: { supported: true, description: 'Save Cypher query to Neo4j via HTTP' },
          processPdf: { supported: true, description: 'Process a PDF file into Neo4j using the GraphRAG pipeline' }

        },
        serverName: 'simple-mcp-fileserver',
        version: '1.0.0',
        mcp: 'filesystem'
      },
      id,
    };
    console.log('Responding to initialize:', JSON.stringify(response));
    return res.json(response);
  } else if (method === 'readFile') {
    fs.readFile(params.path, 'utf8', (err, data) => {
      if (err) {
        const errorResp = { jsonrpc: '2.0', error: { code: 1, message: err.message }, id };
        console.log('readFile error:', JSON.stringify(errorResp));
        return res.json(errorResp);
      }
      const okResp = { jsonrpc: '2.0', result: data, id };
      console.log('readFile success:', JSON.stringify(okResp));
      res.json(okResp);
    });
  } else if (method === 'writeFile') {
    fs.writeFile(params.path, params.content, err => {
      if (err) {
        const errorResp = { jsonrpc: '2.0', error: { code: 1, message: err.message }, id };
        console.log('writeFile error:', JSON.stringify(errorResp));
        return res.json(errorResp);
      }
      const okResp = { jsonrpc: '2.0', result: 'ok', id };
      console.log('writeFile success:', JSON.stringify(okResp));
      res.json(okResp);
    });
  } else if (method === 'listDir') {
    fs.readdir(params.path, (err, files) => {
      if (err) {
        const errorResp = { jsonrpc: '2.0', error: { code: 1, message: err.message }, id };
        console.log('listDir error:', JSON.stringify(errorResp));
        return res.json(errorResp);
      }
      const okResp = { jsonrpc: '2.0', result: files, id };
      console.log('listDir success:', JSON.stringify(okResp));
      res.json(okResp);
    });
  } else if (method === 'readPDF') {
    const pdf = require('pdf-parse');
    try {
      const buffer = fs.readFileSync(params.path);
      pdf(buffer).then(data => {
        const okResp = { jsonrpc: '2.0', result: data.text.slice(0, 3000), id }; // limit to 3000 chars
        console.log('readPDF success:', JSON.stringify(okResp));
        res.json(okResp);
      }).catch(err => {
        const errorResp = { jsonrpc: '2.0', error: { code: 1, message: err.message }, id };
        console.log('readPDF error:', JSON.stringify(errorResp));
        res.json(errorResp);
      });
    } catch (err) {
      const errorResp = { jsonrpc: '2.0', error: { code: 1, message: err.message }, id };
      console.log('readPDF file read error:', JSON.stringify(errorResp));
      res.json(errorResp);
    }
  } else if (method === 'readDocx') {
    const mammoth = require('mammoth');
    try {
      mammoth.extractRawText({ path: params.path }).then(result => {
        const okResp = { jsonrpc: '2.0', result: result.value.slice(0, 3000), id }; // limit content
        console.log('readDocx success:', JSON.stringify(okResp));
        res.json(okResp);
      }).catch(err => {
        const errorResp = { jsonrpc: '2.0', error: { code: 1, message: err.message }, id };
        console.log('readDocx error:', JSON.stringify(errorResp));
        res.json(errorResp);
      });
    } catch (err) {
      const errorResp = { jsonrpc: '2.0', error: { code: 1, message: err.message }, id };
      console.log('readDocx file error:', JSON.stringify(errorResp));
      res.json(errorResp);
    }
  } else if (method === 'readExcel') {
    const xlsx = require('xlsx');
    try {
      const workbook = xlsx.readFile(params.path);
      const sheetName = workbook.SheetNames[0];
      const data = xlsx.utils.sheet_to_json(workbook.Sheets[sheetName], { defval: "" });
      const okResp = { jsonrpc: '2.0', result: data.slice(0, 50), id }; // limit rows
      console.log('readExcel success:', JSON.stringify(okResp));
      res.json(okResp);
    } catch (err) {
      const errorResp = { jsonrpc: '2.0', error: { code: 1, message: err.message }, id };
      console.log('readExcel error:', JSON.stringify(errorResp));
      res.json(errorResp);
    }
  } else if (method === 'get_weather') {
    const axios = require('axios');
    const location = params.location;
    const OPENWEATHER_API_KEY = process.env.OPENWEATHER_API_KEY;
  
    console.log("🛰️ Weather tool called for:", location);
    console.log("🔑 API Key present:", !!OPENWEATHER_API_KEY);
    
    const endpoint = 'https://api.openweathermap.org/data/2.5/weather';
    const weatherParams = {
      q: location,
      appid: OPENWEATHER_API_KEY,
      units: 'imperial'
    };
  
    console.log("📡 Requesting:", endpoint, weatherParams);
  
    axios.get(endpoint, { params: weatherParams })
      .then(response => {
        const data = response.data;
        const weather = {
          location: `${data.name}, ${data.sys.country}`,
          temperature: `${data.main.temp} °F`,
          description: data.weather[0].description.charAt(0).toUpperCase() + data.weather[0].description.slice(1),
          humidity: `${data.main.humidity}%`,
          wind_speed: `${data.wind.speed} mph`
        };
  
        const okResp = { jsonrpc: '2.0', result: weather, id };
        console.log('✅ get_weather success:', JSON.stringify(okResp));
        res.json(okResp);
      })
      .catch(err => {
        const status = err.response?.status || 500;
        const message = err.response?.data?.message || err.message;
        const errorResp = { jsonrpc: '2.0', error: { code: status, message }, id };
        console.log('❌ get_weather error:', JSON.stringify(errorResp));
        res.json(errorResp);
      });
    } else if (method === 'saveToNeo4j') {
      let { cypher } = params;
    
      // ✅ Sanitize the Cypher to avoid multi-statement errors
      cypher = cypher
        .replace(/\bBEGIN\b/gi, '')
        .replace(/\bCOMMIT\b/gi, '')
        .replace(/;/g, '')  // Remove all semicolons
        .trim();
    
      saveToNeo4j(cypher, res, id);
    
    } else if (method === 'processPdf') {
      const { path } = params;
      const { exec } = require('child_process');
    
      console.log(`[MCP] 📄 Processing PDF for Neo4j: ${path}`);
    
      exec(`python3 run_pdf_loader.py "${path}"`, (error, stdout, stderr) => {
        if (error) {
          console.error(`[MCP] ❌ PDF processing error: ${stderr}`);
          const errorResp = {
            jsonrpc: '2.0',
            error: { code: 1, message: stderr },
            id
          };
          return res.json(errorResp);
        }
        console.log(`[MCP] ✅ PDF processing complete`);
        const okResp = {
          jsonrpc: '2.0',
          result: stdout,
          id
        };
        return res.json(okResp);
      });
    
      
        
  } else {
    const errorResp = { jsonrpc: '2.0', error: { code: -32601, message: 'Method not found' }, id };
    console.log('Unknown method:', JSON.stringify(errorResp));
    res.json(errorResp);
  }
});

// Configuration: allow external tool to set port via environment variables
const PORT = process.env.PORT || process.env.MCP_PORT || 8090;

// Simple health‑check endpoint for orchestrators
app.get('/health', (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.send('ok');
});

app.listen(PORT, () => console.log(`MCP FileServer running on port ${PORT}`));
