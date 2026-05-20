from tools.client import ask_client_information


def main() -> None:
    client_info = ask_client_information()
    print(client_info.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
