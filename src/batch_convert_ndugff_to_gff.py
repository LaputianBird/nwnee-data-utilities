import ndu

if __name__ == "__main__":
    app = ndu.App()
    with app.log():
        app.gff.batch.convert_ndugff_to_gff()
