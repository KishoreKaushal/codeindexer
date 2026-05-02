import argparse
from collections import deque
from dataclasses import dataclass
from pprint import pprint
import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser

VERSION = "0.1.0"

def get_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code Indexer CLI")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--cpp", required=True, help="Path to the *.cpp file to index")
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
        return f"{self.kind:<10} {self.fqn:<40} {self.params_sig}{tpl}"


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

def build_fqn_cpp(stack: deque[Scope], name: str) -> str:
    parts = [s.name for s in stack if s.name]
    return "::".join(parts + [name]) \
        if parts else f"::{name}" # if all scopes are anonymous, treat as global
    
def walk_tree_cpp(node, records: list[Record] = [], stack: deque[Scope] = []):
    pushed = False
    if node.type in CPP_SCOPE_NODES:
        name_node = node.child_by_field_name("name")
        
        if node.type != NAMESPACE_DEFINITION and not name_node:
            return # skip anonymous classes/structs since they can't be referred to in the FQN
        
        scope_name = _text(name_node) if name_node else "(anon)" # empty = anonymous scope
        stack.append(Scope(kind=SCOPE_KIND[node.type], name=scope_name))
        pushed = True
    
    if node.type == "function_definition":
        decl = node.child_by_field_name("declarator")
        if decl:
            name_node = decl.child_by_field_name("declarator")
            params_node = decl.child_by_field_name("parameters")
            
            if name_node:
                name = _text(name_node)
                params_sig = _text(params_node) if params_node else "()"
                
                # handle qualified identifier separately
                if name_node.type == "qualified_identifier":
                    name = _text(name_node.child_by_field_name("name"))
                    # build the FQN using the scopes in the stack
                    scope = _text(name_node.child_by_field_name("scope"))
                    fqn = f"{scope}::{name}"
                else:
                    fqn = build_fqn_cpp(stack, name)
                
                kind = get_kind(name, stack)
                
                records.append(Record(fqn=fqn, kind=kind, params_sig=params_sig,
                                      start_point=node.start_point, end_point=node.end_point,
                                      is_template=is_template_fn(node)))
        
    for child in node.children:
        walk_tree_cpp(child, records, stack)
    
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
    stack.append(Scope(kind="global", name=""))
    walk_tree_cpp(tree.root_node, records, stack)
    stack.pop()
    assert len(stack) == 0, "Stack should be empty after processing the tree"
    pprint(records)


def main() -> None:
    parser = get_argparser()
    args = parser.parse_args()
    if args.cpp:
        parse_cpp_file(args.cpp)

if __name__ == "__main__":
    main()