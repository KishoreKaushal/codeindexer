from pathlib import Path
from tree_sitter import Language, Parser
from tree_sitter._binding import Query, QueryCursor
import tree_sitter_cpp as tscpp
from dataclasses import dataclass

QUERIES_DIR = Path(__file__).parent / "queries"

FN_CAPTURE_KEYS = (
    "fn.plain", "fn.qualified", "fn.dtor",
    "fn.refop", "fn.operator", "fn.decl",
    "fn.field_decl"
)

@dataclass
class Record:
    fqn:          str
    kind:         str
    params_sig:   str   = ""
    start_point:  tuple = (0, 0)
    end_point:    tuple = (0, 0)
    is_template:  bool  = False
    is_definition: bool = True
    docstring:    str | None = None

    def __repr__(self):
        tpl  = " :template: " if self.is_template  else ""
        decl = " :decl: "     if not self.is_definition else ""
        return (f"{self.kind:<40} {self.fqn:<50}"
                f" {self.params_sig}{tpl}{decl}")

def _text(node) -> str:
    return node.text.decode("utf-8") if node else ""

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

def _anon_scope_name(node):
    # Walk parent's children for identifier sibling.
    # struct { ... } TestStructType; → "TestStructType"
    if not node.parent:
        return "(anon)"
    for sibling in node.parent.children:
        if sibling.type == "identifier":
            return _text(sibling)
    return "(anon)"

def _collect_scopes(captures):
    scopes = []
    for cap_name, kind in (
        ("scope.ns",     "ns"),
        ("scope.class",  "class"),
        ("scope.struct", "struct"),
    ):
        for node in captures.get(cap_name, []):
            name_node = node.child_by_field_name("name")
            name = (_text(name_node) if name_node
                    else _anon_scope_name(node))
            scopes.append((node.start_byte, node.end_byte,
                           kind, name))

    for cap_name, kind in (
        ("scope.struct.anon", "struct"),
        ("scope.class.anon",  "class"),
    ):
        for node in captures.get(cap_name, []):
            scopes.append((node.start_byte, node.end_byte,
                           kind, _anon_scope_name(node)))

    for node in captures.get("scope.ns.anon", []):
        scopes.append((node.start_byte, node.end_byte,
                       "ns", "(anon)"))

    scopes.sort(key=lambda s: s[0])
    return scopes

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