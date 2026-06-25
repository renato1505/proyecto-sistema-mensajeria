import getpass

from werkzeug.security import generate_password_hash


def main():
    clave = getpass.getpass("Clave a hashear: ")
    confirmar = getpass.getpass("Repetir clave: ")

    if clave != confirmar:
        raise SystemExit("Las claves no coinciden.")

    if not clave:
        raise SystemExit("La clave no puede estar vacia.")

    print(generate_password_hash(clave))


if __name__ == "__main__":
    main()
