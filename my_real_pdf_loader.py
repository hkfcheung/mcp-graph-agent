# my_real_pdf_loader.py
import os
import glob
import asyncio
import csv
import json
import re
from pathlib import Path
from neo4j import GraphDatabase
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from neo4j_graphrag.generation.prompts import ERExtractionTemplate
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# --- Load company names for filtering ---
def load_company_names(csv_path):
    names = set()
    if not Path(csv_path).exists():
        return []
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            name = row.get('name')
            if name:
                names.add(name.strip())
    return sorted(names)

allowed_company_names = load_company_names("data/Company_Filings.csv")
allowed_set = set(name.upper() for name in allowed_company_names)

# --- LLM, embeddings, prompt template ---
embedder = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
llm = OpenAILLM(model_name="gpt-4o", api_key=OPENAI_API_KEY)

joined_names = '\n'.join(f"- {name}" for name in allowed_company_names)
custom_template_text = (
    "Extract only information about the following companies...\n"
    f"Allowed Companies:\n{joined_names}\n\n"
) + ERExtractionTemplate.DEFAULT_TEMPLATE

prompt_template = ERExtractionTemplate(template=custom_template_text)

entities = [
    {"label": "Executive", "properties": [{"name": "name", "type": "STRING"}]},
    {"label": "Product", "properties": [{"name": "name", "type": "STRING"}]},
    {"label": "FinancialMetric", "properties": [{"name": "name", "type": "STRING"}]},
    {"label": "RiskFactor", "properties": [{"name": "name", "type": "STRING"}]},
    {"label": "StockType", "properties": [{"name": "name", "type": "STRING"}]},
    {"label": "Transaction", "properties": [{"name": "name", "type": "STRING"}]},
    {"label": "TimePeriod", "properties": [{"name": "name", "type": "STRING"}]},
    {"label": "Company", "properties": [{"name": "name", "type": "STRING"}]}
]
relations = [
    {"label": "HAS_METRIC"},
    {"label": "FACES_RISK"},
    {"label": "ISSUED_STOCK"},
    {"label": "MENTIONS"}
]

def get_pipeline():
    return SimpleKGPipeline(
        driver=driver,
        llm=llm,
        embedder=embedder,
        entities=entities,
        relations=relations,
        prompt_template=prompt_template,
        enforce_schema="STRICT"
    )

def conform(obj):
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if k == "properties" and v == []:
                new_obj[k] = {}
            else:
                new_obj[k] = conform(v)
        if set(new_obj.keys()) & {"entities", "relations"}:
            allowed_keys = {"entities", "relations"}
            new_obj = {k: v for k, v in new_obj.items() if k in allowed_keys}
            if "entities" not in new_obj or not isinstance(new_obj["entities"], list):
                new_obj["entities"] = []
            if "relations" not in new_obj or not isinstance(new_obj["relations"], list):
                new_obj["relations"] = []
        return new_obj
    elif isinstance(obj, list):
        return [conform(item) for item in obj]
    else:
        return obj

def safe_json_loads_and_conform(content):
    try:
        return conform(json.loads(content))
    except Exception:
        return None

async def run_pipeline_on_file(file_path: str, pipeline):
    print(f"[INFO] Processing file: {file_path}")
    try:
        result = await pipeline.run_async(file_path=file_path)
        parsed = safe_json_loads_and_conform(result.llm_output)
        if parsed:
            print("[INFO] Successfully conformed LLM output")
        else:
            print("[WARNING] LLM output could not be conformed")
        return parsed
    except Exception as e:
        print(f"[ERROR] Pipeline failed on {file_path}: {e}")
        return None
