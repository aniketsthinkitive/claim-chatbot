from pageindex import PageIndexClient


class DocumentProcessor:
    def __init__(self, api_key: str):
        self.client = PageIndexClient(api_key=api_key)

    def index_document(self, pdf_path: str) -> str:
        result = self.client.submit_document(pdf_path)
        return result["doc_id"]

    def get_document_tree(self, doc_id: str) -> dict:
        result = self.client.get_tree(doc_id, node_summary=True)
        return result["result"]

    def get_document_text(self, doc_id: str) -> str:
        tree = self.get_document_tree(doc_id)
        return self._tree_to_text(tree)

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
