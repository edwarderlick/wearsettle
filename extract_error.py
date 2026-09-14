import re
import sys

def main():
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        txt = f.read()
    
    match = re.search(r'"error_data"\s*:\s*"([^"]+)"', txt)
    if match:
        error_hex = match.group(1)
        if error_hex.startswith("0x"):
            error_hex = error_hex[2:]
        try:
            print(bytes.fromhex(error_hex).decode('utf-8', errors='replace'))
        except Exception as e:
            print(f"Failed to decode: {e}")
    else:
        print("error_data not found in json logs")

if __name__ == '__main__':
    main()
