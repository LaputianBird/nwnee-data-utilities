import ndu

if __name__ == "__main__":
    app = ndu.App()
    with app.log():
        app.gff.batch.convert_json_to_ndugff()
