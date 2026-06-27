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

def build_scope_kind_table(captures):
    table = {}
    for cap_name, kind in (
        ("scope.ns.name",     "ns"),
        ("scope.class.name",  "class"),
        ("scope.struct.name", "struct"),
    ):
        for node in captures.get(cap_name, []):
            table[_text(node)] = kind
    return table

def _build_fqn(enclosing, name,
               scope_kind_table, extra_scopes=None):
    parts = [n for _, n in enclosing]
    if extra_scopes:
        parts.extend(extra_scopes)
    parts.append(name)
    if not parts[:-1]:
        return f"::{name}"   # global — prepend ::
    return "::".join(parts)

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
    
    
def _enclosing_scopes(scopes, start_byte, end_byte):
    return [(kind, name) for s, e, kind, name in scopes if s <= start_byte <= end_byte <= e]

def _classify_kind(name, enclosing, scope_kind_table, extra_scopes=None):
    if extra_scopes:
        tail = extra_scopes[-1] 
        tail_kind = scope_kind_table.get(tail) 
        if tail_kind in ("class", "struct"):
            return "ctor" if name == tail else "method"
        return "free_fn"
        
    for kind, scope_name in reversed(enclosing):
        if kind in ("class", "struct"):
            return "ctor" if name == scope_name else "method"
        
    return "free_fn"

def _split_qualified(name_node):
    parts = []
    node = name_node
    while node.type == "qualified_identifier":
        scope = node.child_by_field_name("scope")
        parts.append(_text(scope))
        node = node.child_by_field_name("name")
    
    return parts, _text(node)
    
def bind_captures(captures, scope_kind_table,
                  src: bytes) -> list[Record]:
    scopes    = _collect_scopes(captures)
    templates = captures.get("mod.template", [])
    friends   = captures.get("mod.friend",   [])

    # collect ALL fn nodes across every capture key
    # so attach_docstrings sees the full set
    all_fn_nodes = [
        n for k in FN_CAPTURE_KEYS
        for n in captures.get(k, [])
    ]
    docstrings = attach_docstrings(captures, all_fn_nodes, src)

    seen    = set()    # (fqn, params_sig) — dedup key
    records = []


    def __extract_capture_internal_to_fn_node(fn, name_cap_keys):
        name_node = next(
            (n for n in captures.get(name_cap_keys, []) if (fn.start_byte <= n.start_byte <= n.end_byte <= fn.end_byte)),
            None
        )
        return name_node

    # --- fn.plain loop (next slide) ---
    for fn_node in captures.get("fn.plain", []):
        name_node = __extract_capture_internal_to_fn_node(fn_node, "name.plain")
        if not name_node: continue
        params_node = __extract_capture_internal_to_fn_node(fn_node, "params")
        params_sig = _text(params_node) if params_node else "()"
        name = _text(name_node)
        
        enclosing = _enclosing_scopes(scopes, fn_node.start_byte, fn_node.end_byte)
        is_template = _is_inside_any(fn_node, templates)
        is_friend = _is_inside_any(fn_node, friends)
        
        if is_friend:
            kind = "friend_operator" if name_node.type == "operator_name" else "friend"
            ns_enclosing = [(k, n) for k, n in enclosing if k == "ns"]
            fqn = _build_fqn(ns_enclosing, name, scope_kind_table)
        else:
            kind = _classify_kind(name, enclosing, scope_kind_table)
            fqn = _build_fqn(enclosing, name, scope_kind_table)
            
        sig = (fqn, params_sig)
        if sig in seen:
            continue
        seen.add(sig)
        
        records.append(Record(
            fqn=fqn,
            kind=kind,
            params_sig=params_sig,
            start_point=fn_node.start_point,
            end_point=fn_node.end_point,
            is_template=is_template,
            is_definition=True,
            docstring=docstrings.get(fn_node.start_byte)
        ))
    

        
    # --- fn.qualified loop           ---
    for fn_node in captures.get("fn.qualified", []):
        # X::Y::z()
        name_node = __extract_capture_internal_to_fn_node(fn_node, "name.qual")
        if not name_node: continue
        params_node = __extract_capture_internal_to_fn_node(fn_node, "params")
        params_sig = _text(params_node) if params_node else "()"
        extra_scopes, name = _split_qualified(name_node)
        
        enclosing = _enclosing_scopes(scopes, fn_node.start_byte, fn_node.end_byte)
        is_template = _is_inside_any(fn_node, templates)
        
        kind = _classify_kind(name, enclosing, scope_kind_table, extra_scopes=extra_scopes)
        fqn = _build_fqn(enclosing, name, scope_kind_table, extra_scopes=extra_scopes)
        
        sig = (fqn, params_sig)
        if sig in seen:
            continue
        seen.add(sig)
        
        records.append(Record(
            fqn=fqn,
            kind=kind,
            params_sig=params_sig,
            start_point=fn_node.start_point,
            end_point=fn_node.end_point,
            is_template=is_template,
            is_definition=True,
            docstring=docstrings.get(fn_node.start_byte)
        ))
        

    
    # --- fn.dtor loop                ---
    for fn_node in captures.get("fn.dtor", []):
        name_node = __extract_capture_internal_to_fn_node(fn_node, "name.dtor")
        if not name_node: continue
        params_node = __extract_capture_internal_to_fn_node(fn_node, "params")
        params_sig = _text(params_node) if params_node else "()"
        name = _text(name_node)
        
        enclosing = _enclosing_scopes(scopes, fn_node.start_byte, fn_node.end_byte)
        fqn = _build_fqn(enclosing, name, scope_kind_table)
        
        sig = (fqn, params_sig)
        if sig in seen:
            continue
        seen.add(sig)
        
        records.append(Record(
            fqn=fqn,
            kind="dtor",
            params_sig=params_sig,
            start_point=fn_node.start_point,
            end_point=fn_node.end_point,
            is_template=False,
            is_definition=True,
            docstring=docstrings.get(fn_node.start_byte)
        ))
    
    
    
    # --- fn.operator loop            ---
    for fn_node in captures.get("fn.operator", []):
        name_node = __extract_capture_internal_to_fn_node(fn_node, "name.operator")
        if not name_node: continue
        params_node = __extract_capture_internal_to_fn_node(fn_node, "params")
        params_sig = _text(params_node) if params_node else "()"
        name = _text(name_node)
        
        enclosing = _enclosing_scopes(scopes, fn_node.start_byte, fn_node.end_byte)
        fqn = _build_fqn(enclosing, name, scope_kind_table)
        
        sig = (fqn, params_sig)
        if sig in seen:
            continue
        seen.add(sig)
        
        records.append(Record(
            fqn=fqn,
            kind="operator",
            params_sig=params_sig,
            start_point=fn_node.start_point,
            end_point=fn_node.end_point,
            is_template=False,
            is_definition=True,
            docstring=docstrings.get(fn_node.start_byte)
        ))
    
    
    # --- fn.refop loop               ---
    for fn_node in captures.get("fn.refop", []):
        name_node = __extract_capture_internal_to_fn_node(fn_node, "name.refop")
        if not name_node: continue
        params_node = __extract_capture_internal_to_fn_node(fn_node, "params")
        params_sig = _text(params_node) if params_node else "()"
        name = _text(name_node)
        
        enclosing = _enclosing_scopes(scopes, fn_node.start_byte, fn_node.end_byte)
        is_friend = _is_inside_any(fn_node, friends)
        kind = "friend_refop" if is_friend else "refop"
        
        ns_enclosing = [(k, n) for k, n in enclosing if k == "ns"]
        
        fqn = _build_fqn(ns_enclosing, name, scope_kind_table)
        
        sig = (fqn, params_sig)
        if sig in seen:
            continue
        seen.add(sig)
        
        records.append(Record(
            fqn=fqn,
            kind=kind,
            params_sig=params_sig,
            start_point=fn_node.start_point,
            end_point=fn_node.end_point,
            is_template=False,
            is_definition=True,
            docstring=docstrings.get(fn_node.start_byte)
        ))

    
    # --- fn.decl loop                ---
    for fn_node in captures.get("fn.decl", []):
        name_node = __extract_capture_internal_to_fn_node(fn_node, "name.decl")
        if not name_node: continue
        params_node = __extract_capture_internal_to_fn_node(fn_node, "params.decl")
        params_sig = _text(params_node) if params_node else "()"
        name = _text(name_node)
        
        is_qualified = name_node.type == "qualified_identifier"
        
        extra_scopes = None
        if is_qualified:
            extra_scopes, name = _split_qualified(name_node)
        
        enclosing = _enclosing_scopes(scopes, fn_node.start_byte, fn_node.end_byte)
        kind = _classify_kind(name, enclosing, scope_kind_table, extra_scopes=extra_scopes)
        fqn = _build_fqn(enclosing, name, scope_kind_table, extra_scopes=extra_scopes)
        
        sig = (fqn, params_sig)
        
        records.append(Record(
            fqn=fqn,
            kind=kind,
            params_sig=params_sig,
            start_point=fn_node.start_point,
            end_point=fn_node.end_point,
            is_template=False,
            is_definition=False,
            docstring=docstrings.get(fn_node.start_byte)
        ))
        
    return records
    
    # --- fn.field_decl loop          ---
    for fn_node in captures.get("fn.field_decl", []):
        name_node = __extract_capture_internal_to_fn_node(fn_node, "name.field_decl")
        if not name_node: continue
        params_node = __extract_capture_internal_to_fn_node(fn_node, "params.field_decl")
        params_sig = _text(params_node) if params_node else "()"
        name = _text(name_node)
        pass

    return records