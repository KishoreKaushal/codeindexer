from pathlib import Path
from tree_sitter import Language, Parser
from tree_sitter._binding import Query, QueryCursor
import tree_sitter_cpp as tscpp

QUERIES_DIR = Path(__file__).parent / "queries"


FN_CAPTURE_KEYS = [
    "fn.plain",
    "fn.qualified",
    "fn.dtor",
    "fn.refop",
    "fn.field_decl",
    "fn.decl",
    "fn.operator"
]

def _is_inside_any(fn_node, mod_nodes):
    for mod in mod_nodes:
        if (mod.start_byte <= fn_node.start_byte
                and fn_node.end_byte <= mod.end_byte):
            return True
    return False

def _text(node) -> str:
    return node.text.decode("utf-8") if node else ""

def _strip_comment_markers(text: str) -> str:
    lines = text.split("\n")
    out = []
    for line in lines:
        line = line.strip()
        if line.startswith("//"):
            out.append(line[2:].strip())
        elif line.startswith("/**") or line.startswith("/*"):
            out.append(line.lstrip("/*").rstrip("/*").strip())
        elif line.startswith("*/"):
            continue
        elif line.startswith("*"):
            out.append(line[1:].strip())
        else:
            out.append(line)
    return " ".join(s for s in out if s)

def attach_docstrings(captures, fn_captures, src: bytes):
    src_lines = src.split(b"\n")
    comments = sorted(captures.get("comment", []),
                      key=lambda c: c.end_byte)
    out = {}
    for fn_node in fn_captures:
        fn_start = fn_node.start_byte
        for c in reversed(comments):
            if c.end_byte > fn_start: # checking whether comment is above the function
                continue
            
            # reject trailing / same-line comments
            comment_line = src_lines[c.start_point[0]]
            if comment_line[:c.start_point[1]].strip():
                continue
            # reject if intervening non-blank, non-comment lines
            gap = src_lines[c.end_point[0]+1:fn_node.start_point[0]]
            if any(l.strip() and not l.strip().startswith(b"//")
                   for l in gap):
                continue
            # reject if function doesn't start its own line
            fn_line = src_lines[fn_node.start_point[0]]
            if fn_line[:fn_node.start_point[1]].strip():
                continue
            out[fn_start] = _strip_comment_markers(_text(c))
            break
    return out

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