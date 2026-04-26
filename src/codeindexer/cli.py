import argparse

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
            print(f.read())
    print("Hello from codeindexer cli!")


if __name__ == "__main__":
    main()