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

def walk_tree_cpp(node, records: list[Record] = [], stack: deque[Scope] = []):
    # current scope name is top of the stack if stack is not empty
    # otherwise it's empty string
    current_scope_name = stack[-1].name if stack else ""
    if node.type == "function_definition":
        node_name = node.child_by_field_name("declarator")
        if node_name:
            # if current scope name is there we prefix it 
            # otherwise we just take the function name as is
            fqn = (current_scope_name + "::" + node_name.text.decode('utf-8')) \
                if current_scope_name else node_name.text.decode('utf-8')
                    
            records.append(Record(fqn=fqn))
        
        print(f"Found function: {node_name.text.decode('utf-8')}")
    
    # handle the scope while entering the children
    for child in node.children:
        # append some scope to the stack
        scope_name = stack[-1].name + "::" + node.type \
            if stack else node.type # if stack is empty we just take the node type as scope name
        stack.append(Scope(kind=node.type, name=scope_name))
        walk_tree_cpp(child, records, stack)
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