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

def main() -> None:
    parser = get_argparser()
    args = parser.parse_args()
    if args.cpp:
        print(f"Indexing C++ file: {args.cpp}")
        with open(args.cpp, 'rb') as f:
            code_bytes = f.read()
            
        CPP_LANGUAGE = Language(tscpp.language())
        parser = Parser(CPP_LANGUAGE)
        tree = parser.parse(code_bytes)
        print(tree)
    print("Hello from codeindexer cli!")


if __name__ == "__main__":
    main()