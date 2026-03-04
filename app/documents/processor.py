import time
import logging

from pageindex import PageIndexClient

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self, api_key: str):
        self.client = PageIndexClient(api_key=api_key)

    def index_document(self, pdf_path: str) -> str:
        result = self.client.submit_document(pdf_path)
        return result["doc_id"]

    def wait_until_ready(self, doc_id: str, max_wait: int = 60, poll_interval: int = 3) -> bool:
        """Poll PageIndex until document processing is complete."""
        elapsed = 0
        while elapsed < max_wait:
            result = self.client.get_tree(doc_id, node_summary=False)
            status = result.get("status", "")
            if status == "completed" and result.get("retrieval_ready"):
                logger.info(f"Document {doc_id} ready after {elapsed}s")
                return True
            if status == "failed":
                logger.error(f"Document {doc_id} processing failed")
                return False
            logger.info(f"Document {doc_id} status: {status}, waiting...")
            time.sleep(poll_interval)
            elapsed += poll_interval
        logger.warning(f"Document {doc_id} timed out after {max_wait}s")
        return False

    def get_document_tree(self, doc_id: str) -> dict:
        result = self.client.get_tree(doc_id, node_summary=True)
        tree_data = result.get("result")
        if not tree_data:
            return {}
        # result can be a list of root nodes or a single dict
        if isinstance(tree_data, list):
            return tree_data[0] if tree_data else {}
        return tree_data

    def get_document_text(self, doc_id: str) -> str:
        tree = self.get_document_tree(doc_id)
        if not tree:
            return ""
        return self._tree_to_text(tree)

    def get_document_ocr(self, doc_id: str) -> str:
        result = self.client.get_ocr(doc_id, format="raw")
        return result.get("result", "")

    def _tree_to_text(self, node: dict, depth: int = 0) -> str:
        lines = []
        indent = "  " * depth
        title = node.get("title", "")
        summary = node.get("summary", "")
        if title:
            lines.append(f"{indent}{title}")
        if summary:
            lines.append(f"{indent}  {summary}")
        for child in node.get("children", []):
            lines.append(self._tree_to_text(child, depth + 1))
        return "\n".join(lines)
