# run_pdf_loader.py
import sys
from pathlib import Path
from your_pdf_loader_module import get_pipeline, run_pipeline_on_file  # Adjust imports to match your actual module structure
import asyncio

def main(pdf_path):
    pipeline = get_pipeline()  # Your function that returns the configured SimpleKGPipeline
    asyncio.run(run_pipeline_on_file(pdf_path, pipeline))

if __name__ == "__main__":
    pdf_path = sys.argv[1]
    main(pdf_path)
