import socket, argparse, json, time

parser = argparse.ArgumentParser()
parser.add_argument("--topic", required=True)
parser.add_argument("--limit", type=int, default=50)
parser.add_argument("--broker-host", default="127.0.0.1")
parser.add_argument("--broker-port", type=int, default=7777)
args = parser.parse_args()

def fetch_history():
    with socket.create_connection((args.broker_host, args.broker_port)) as s:
        s.sendall(f"HISTORY {args.topic} {args.limit}\n".encode())
        data = s.recv(1_000_000).decode()
    return json.loads(data)

if __name__ == "__main__":
    while True:
        hist = fetch_history()
        print("---- HISTORY ----")
        for m in hist:
            print(f"[off={m.get('offset')} ts={m.get('ts')}] {m['from']}→{m['to']}: {m['text']} (id={m['id']})")
        time.sleep(2)