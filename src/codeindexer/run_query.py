from pathlib import Path
from tree_sitter import Language, Parser
from tree_sitter._binding import Query, QueryCursor
import tree_sitter_cpp as tscpp

QUERIES_DIR = Path(__file__).parent / "queries"

def load_query(language: Language,
               lang_name: str) -> Query:
    scm = QUERIES_DIR / f"{lang_name}.scm"
    return Query(language, scm.read_text())


def parse_file(file_path: str) -> dict:
    with open(file_path, 'rb') as f:
        src = f.read()
    CPP_LANGUAGE = Language(tscpp.language())
    tree = Parser(CPP_LANGUAGE).parse(src)
    query = load_query(CPP_LANGUAGE, "cpp")
    caps = QueryCursor(query).captures(tree.root_node)
    return {"lang": "cpp", "src": src,
            "tree": tree, "captures": caps}