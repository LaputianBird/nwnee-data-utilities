import ndu

if __name__ == "__main__":
    app = ndu.App()
    with app.log():
        app.erf.batch.create_erf_from_folder()
