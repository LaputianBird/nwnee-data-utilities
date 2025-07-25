import ndu

if __name__ == "__main__":
    app = ndu.App()
    with app.log():
        app.erf.batch.extract_erf_to_folder()
