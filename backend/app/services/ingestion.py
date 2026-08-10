"""
Sentinel ingestion pipeline.

Loads runbook (store-> how to fix)/postmortem (store -> what went wrong) markdown files, splits them into chunks, embeds 
them, and persists a local Chroma vector store.

Run directly from the `backend/` directory with:
    python -m app.services.ingestion

Optional flags:
    python -m app.services.ingestion --chunk-size 1200 --chunk-overlap 150 --rebuild
"""

import argparse
import logging
import sys
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

logging.basicConfig(
    level = logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sentinel.ingestion")

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "runbooks"
DEFAULT_PERSIST_DIR = Path(__file__).resolve().parents[3] / "chroma_sentinel"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def load_runbooks(data_dir: Path):
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Runbook directory not found: {data_dir}. "
            "Create it and add at least one .md file before runningingestion."
        )

    loader = DirectoryLoader(
        str(data_dir),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    docs = loader.load()

    if not docs:
        raise ValueError(
            f"No markdown files found in {data_dir}. "
            "Ingestion requires at least one runbook to build a usable vector store."
        )

    logger.info("Loaded %d source document(s) from %s", len(docs), data_dir)
    return docs


def split_documents(docs, chunk_size: int, chunk_overlap: int):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size = chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    logger.info(
        "Split %d document(s) into %d chunk(s) (chunk_size=%d, overlap=%d)",
        len(docs), len(chunks), chunk_size, chunk_overlap,
    )
    return chunks

def build_vectorstore(chunks, persist_dir: Path, rebuild: bool):
    if rebuild and persist_dir.exists():
        import shutil  #❓❓❓❓
        logger.warning("Rebuild flag set - deleting existing store at %s", persist_dir)
        shutil.rmtree(persist_dir)

    logger.info("Loading embedding model: %s (first run downloads it, cached after)", EMBEDDING_MODEL)
    embeddings = HuggingFaceEmbeddings(model_name = EMBEDDING_MODEL)

    logger.info("Embedd %d chunk(s) and persisting to %s", len(chunks), persist_dir)
    vectorstore = Chroma.from_documents(
        documents = chunks,
        embedding = embeddings,
        persist_directory=str(persist_dir),
    )
    logger.info("Vector store ready at %s", persist_dir)
    return vectorstore

def run_ingestion(
    data_dir: Path = DEFAULT_DATA_DIR,
    persist_dir: Path = DEFAULT_PERSIST_DIR,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    rebuild: bool = False,
):
    try:
        docs = load_runbooks(data_dir)
        chunks = split_documents(docs, chunk_size, chunk_overlap)
        build_vectorstore(chunks, persist_dir, rebuild)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Ingestion aborted: %s", exc)
        sys.exit(1)
    except Exception:
        logger.exception("Unexpected error during ingestion")
        sys.exit(1)

def parse_args():
    parser = argparse.ArgumentParser(description="Sentinel runbook ingestion pipeline")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--persist-dir", type=Path, default=DEFAULT_PERSIST_DIR)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("-chunk-overlap", type=int, default=200)
    parser.add_argument("--rebuild", action="store_true", help="Delete and recreate the store from scratch")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run_ingestion(
        data_dir=args.data_dir,
        persist_dir=args.persist_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        rebuild=args.rebuild,
    )

