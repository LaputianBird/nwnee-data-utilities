import ndu

if __name__ == "__main__":
    app = ndu.App()
    with app.log():
        app.gff.batch.convert_gff_to_ndugff()
