import ndu

if __name__ == "__main__":
    app = ndu.App()
    with app.log():
        app.keybif.export_game_resources()
