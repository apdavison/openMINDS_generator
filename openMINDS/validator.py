import sys
import jsonschema


def main(json_ld_filename):
    print(json_ld_filename)

def print_help():
    print("Usage:")
    print("validator <json-ld-file>")

def verify_parameters(argv):
    if len(argv) != 2:
        print("Wrong number of arguments")
        print_help()
        sys.exit(1)

if __name__ == "__main__":
    verify_parameters(sys.argv)
    main(sys.argv[1])
