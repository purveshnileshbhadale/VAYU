import sys

def main() -> int:
    """
    Main function to print "Hello World".
    Returns 0 on success, 1 on error.
    """
    try:
        print("Hello World")
        return 0
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    # Execute the main function and use its return value as the script's exit code.
    sys.exit(main())