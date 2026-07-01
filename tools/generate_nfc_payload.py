"""Generate SmartParcelStation NFC NDEF URI payloads."""

import argparse
from urllib.parse import urlencode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an SPS NFC URI payload")
    subparsers = parser.add_subparsers(dest="payload_type", required=True)

    gate = subparsers.add_parser("gate-nfc", help="generate a gate NFC tag URI")
    gate.add_argument("--gateway-code", required=True)
    gate.add_argument("--reader-id", required=True)
    gate.add_argument("--station-id", required=True)
    gate.add_argument("--gate-nfc-tag-id", required=True)

    pickup = subparsers.add_parser("pickup", help="generate a parcel pickup NFC tag URI")
    pickup.add_argument("--tag-id", required=True)
    pickup.add_argument("--pickup-binding-id", required=True)
    pickup.add_argument("--encrypted-token", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.payload_type == "gate-nfc":
        query = urlencode(
            {
                "v": "1",
                "gateway_code": args.gateway_code,
                "reader_id": args.reader_id,
                "station_id": args.station_id,
                "gate_nfc_tag_id": args.gate_nfc_tag_id,
            }
        )
        print(f"sps://gate-nfc?{query}")
    else:
        query = urlencode(
            {
                "v": "1",
                "tag_id": args.tag_id,
                "binding": args.pickup_binding_id,
                "token": args.encrypted_token,
            }
        )
        print(f"sps://pickup?{query}")


if __name__ == "__main__":
    main()
