import argparse
import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser

VERSION = "0.1.0"

def get_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code Indexer CLI")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--cpp", required=True, help="Path to the *.cpp file to index")
    # Add arguments here as needed
    return parser

def walk_tree_cpp(node):
    if node.type == "function_definition":
        node_name = node.child_by_field_name("declarator")
        print(f"Found function: {node_name.text.decode('utf-8')}")
    
    for child in node.children:
        walk_tree_cpp(child)

def parse_cpp_file(file_path: str) -> None:
    with open(file_path, 'rb') as f:
        code_bytes = f.read()
        
    CPP_LANGUAGE = Language(tscpp.language())
    parser = Parser(CPP_LANGUAGE)
    tree = parser.parse(code_bytes)
    walk_tree_cpp(tree.root_node)

def main() -> None:
    parser = get_argparser()
    args = parser.parse_args()
    if args.cpp:
        parse_cpp_file(args.cpp)

if __name__ == "__main__":
    main()