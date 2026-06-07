import argparse
from collections import deque
from dataclasses import dataclass
from pprint import pprint
from rich import print
import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser

VERSION = "0.1.0"

def get_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code Indexer CLI")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--cpp", required=True, help="Path to the *.cpp file to index")
    parser.add_argument("--query", action="store_true", help="Use query based parsing")
    # Add arguments here as needed
    return parser

@dataclass
class Scope:
    kind: str  # "ns" | "class" | "function"
    name: str  # "" for anonymous scopes
    
@dataclass 
class Record:
    fqn: str # fully qualified name, e.g. "math::Adder::sum"
    kind: str # "method" | "frunction" | "ctor"
    params_sig: str = "" # e.g. "(int, int)" for sum(int a, int b)
    start_point: tuple[int, int] = (0, 0) # (line, column)
    end_point: tuple[int, int] = (0, 0)
    is_template: bool = False # whether it's a template function/method
    
    def __repr__(self):
        tpl = " [template]" if self.is_template else ""
        return f"{self.kind:<40} {self.fqn:<50} {self.params_sig}{tpl}"

# frozen makes hashable and slots saves memory -> go look chatgpt for more details
@dataclass(frozen=True, slots=True)
class FuncSig:
    fqn: str 
    params_sig: str

def get_kind(name: str, stack: deque[Scope]) -> str:
    # brief logic: look from start of the scope 
    # if the current kind is either class or struct and the name matches
    # => ctor, else method 
    # no class/struct => function
    for s in reversed(stack):
        # remember that in a C++ code stack 
        # stack will of of form: [ns*, class/struct*]
        # as there is no namespace inside class/struct
        if s.kind in ("class", "struct"): 
            if s.name == name:
                return "ctor"
            return "method"
    return "function"


def _text(node) -> str:
    return node.text.decode('utf-8') if node else "" # safe extraction

def is_template_fn(node) -> bool:
    return node.parent and node.parent.type == "template_declaration"

NAMESPACE_DEFINITION = "namespace_definition"
CLASS_SPECIFIER = "class_specifier"
STRUCT_SPECIFIER = "struct_specifier"
CPP_SCOPE_NODES = (NAMESPACE_DEFINITION, CLASS_SPECIFIER, STRUCT_SPECIFIER)
SCOPE_KIND = {
    NAMESPACE_DEFINITION: "ns",
    CLASS_SPECIFIER: "class",
    STRUCT_SPECIFIER: "struct"
}

def build_fqn_cpp(stack: deque[Scope], name: str, extra_scopes: list[str] = None, friend_flag: bool = False) -> str:
    if friend_flag:
        # for friend functions, we only consider namespaces in the scope for FQN 
        # since they can't be referred to via class/struct scopes
        scopes = [s.name for s in stack if s.kind == "ns" and s.name]
    else:
        scopes = [s.name for s in stack if s.name]
        
    if extra_scopes:
        scopes.extend(extra_scopes)
    
    return "::".join(scopes + [name]) \
        if scopes else f"::{name}" # if all scopes are anonymous, treat as global

def _classify_and_record(name_node, params_node, node, records, stack, seen, friend_flag=False):
    name = _text(name_node)
    params_sig = _text(params_node) if params_node else "()"
    
    # handle qualified identifier separately
    if name_node.type == "qualified_identifier":
        name = _text(name_node.child_by_field_name("name"))
        scope = _text(name_node.child_by_field_name("scope"))
        fqn = build_fqn_cpp(stack, name, extra_scopes=[scope], friend_flag=friend_flag)
        kind = "friend" if friend_flag else get_kind(name, stack)
    elif name_node.type == "operator_name":
        kind = "friend_operator" if friend_flag else "operator"
        fqn = build_fqn_cpp(stack, name, friend_flag=friend_flag)
    elif name_node.type == "destructor_name":
        kind = "dtor"
        fqn = build_fqn_cpp(stack, name, friend_flag=friend_flag)
    else:
        fqn = build_fqn_cpp(stack, name, friend_flag=friend_flag)
        kind = "friend" if friend_flag else get_kind(name, stack)
    
    func_sig = FuncSig(fqn=fqn, params_sig=params_sig)
    
    if func_sig in seen:
        return # skip duplicate
    
    records.append(Record(fqn=fqn, 
                            kind=kind, 
                            params_sig=params_sig,
                            start_point=node.start_point, 
                            end_point=node.end_point,
                            is_template=is_template_fn(node)))
    seen.add(func_sig)
    
def get_anon_struct_name(node) -> str | None:
    # heuristic to get the name of an anonymous struct/class:
    # look for an identifier among the siblings of the node
    # this works for cases like: "struct { ... } myVar;" or "class { ... } MyClass;"
    if node.parent:
        for sibling in node.parent.children:
            if sibling.type == "identifier":
                return _text(sibling)
    return None

def walk_tree_cpp(node, 
                  records: list[Record] = [], 
                  stack: deque[Scope] = [], 
                  seen: set[FuncSig] = set(),
                  friend_flag: bool = False) -> None:
    pushed = False
    
    if node.type == "friend_declaration":
        friend_flag = True # set the flag to indicate we're inside a friend declaration
    
    if node.type in CPP_SCOPE_NODES:
        name_node = node.child_by_field_name("name")
        
        if node.type != NAMESPACE_DEFINITION and not name_node:
            scope_name = get_anon_struct_name(node)
            if scope_name is None:
                return # skip if we can't determine a name for the anonymous struct/class
        else:
            scope_name = _text(name_node) if name_node else "(anon)" # empty = anonymous scope
        
        stack.append(Scope(kind=SCOPE_KIND[node.type], name=scope_name))
        pushed = True
    
    if node.type == "function_definition":
        decl = node.child_by_field_name("declarator")
        if decl:
            name_node = decl.child_by_field_name("declarator")
            params_node = decl.child_by_field_name("parameters")
            
            if name_node:
                _classify_and_record(name_node, params_node, node, records, stack, seen, friend_flag=friend_flag)

    elif node.type == "function_declarator":
        if node.parent and node.parent.type == "function_definition":
            return # skip since it's already handled in the function_definition case        
        name_node = node.child_by_field_name("declarator")
        params_node = node.child_by_field_name("parameters")
        if name_node:
            _classify_and_record(name_node, params_node, node, records, stack, seen, friend_flag=friend_flag)
       
    for child in node.children:
        walk_tree_cpp(child, records, stack, seen, friend_flag=friend_flag)
    
    if pushed:
        stack.pop() # pop the scope after processing the children

def parse_cpp_file(file_path: str) -> None:
    with open(file_path, 'rb') as f:
        code_bytes = f.read()
        
    CPP_LANGUAGE = Language(tscpp.language())
    parser = Parser(CPP_LANGUAGE)
    tree = parser.parse(code_bytes)
    records: list[Record] = []
    stack: deque[Scope] = deque()
    seen: set[FuncSig] = set() # de-duplication
    stack.append(Scope(kind="global", name=""))
    walk_tree_cpp(tree.root_node, records, stack, seen)
    stack.pop()
    assert len(stack) == 0, "Stack should be empty after processing the tree"
    pprint(records)


def main() -> None:
    parser = get_argparser()
    args = parser.parse_args()
    if args.cpp:
        if args.query:
            from codeindexer.run_query import parse_file, attach_docstrings, FN_CAPTURE_KEYS
            result = parse_file(args.cpp)
            # pprint(result)
            caps = result["captures"]
            src = result["src"]
            
            for cap_name, nodes in sorted(caps.items()):
                print(f"[bold italic cyan]@{cap_name}[/bold italic cyan]: {len(nodes)} matches")
                for n in nodes:
                    print(f"    [{n.start_point[0] + 1}, {n.start_point[1]+1}] {n.text.decode()[:60]}")
            
            fn_captures = [n for k in FN_CAPTURE_KEYS for n in caps.get(k, [])]
            fn_captures = sorted(fn_captures, key=lambda n: n.start_byte)
            docstrings = attach_docstrings(caps, fn_captures, src)
            print(docstrings)
            
            for fn in fn_captures:
                ds = docstrings.get(fn.start_byte) or "<no docstring found>"
                print(f"  L{fn.start_point[0]+1}: {ds}")
        else:
            parse_cpp_file(args.cpp)

if __name__ == "__main__":
    main()