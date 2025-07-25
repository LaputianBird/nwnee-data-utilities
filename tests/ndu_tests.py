import sys
from pathlib import Path
src_dp = Path(__file__).resolve().parent.parent / "src"
if str(src_dp) not in sys.path:
    sys.path.insert(0, str(src_dp))

def main():
    import subprocess
    import ndu

    def convert_gff_to_nim_json(arg_input_root=None, arg_output_root=None):
        input_validator = ndu._Paths.get_is_gff_file
        def output_namer(arg_input_fp): return f"nimjson__{arg_input_fp.name}.json"
        fp_pairs = ndu._Paths._get_nested_path_pairs(
            arg_input_root, arg_output_root, input_validator, output_namer
        )
        for input_fp, output_fp in fp_pairs:
            subprocess.run(
                [
                    str(Path(__file__).parent / "nwn_gff"),
                    '-i', str(input_fp),
                    '-o', str(output_fp),
                    '-p',
                ],
                universal_newlines=True
            )

    def convert_json_to_nim_gff(arg_input_root=None, arg_output_root=None):
        input_validator = ndu._Paths.get_is_json_file
        def output_namer(arg_input_fp): return f"nimgff__{arg_input_fp.stem}"
        fp_pairs = ndu._Paths._get_nested_path_pairs(
            arg_input_root, arg_output_root, input_validator, output_namer
        )
        for input_fp, output_fp in fp_pairs:
            subprocess.run(
                [
                    str(Path(__file__).parent / "nwn_gff"),
                    '-i', str(input_fp),
                    '-o', str(output_fp),
                ],
                universal_newlines=True
            )

    app = ndu.App()
    with app.log():
        data_dp = ndu._Paths._get_default_data_dp()
        paths = {
            name: data_dp / name
            for name in [
                "gff/0_from_gff",
                "gff/1_to_json",
                "gff/2_to_ndugff",
                "gff/3_to_gff",
                "gff/4_to_ndugff",
                "gff/5_to_json",
                "gff/6_to_gff",
                "erf/0_from_erf",
                "erf/1_to_folder",
                "erf/2_to_erf",
                "erf/3_to_folder",
                "erf/4_to_erf",
                "keybif"
            ]
        }
        for dp in paths.values():
            dp.mkdir(parents=True, exist_ok=True)

        if False:
            (app.gff.single
                .load_gff(paths["gff/0_from_gff"] / "narwikhorlabur.bic")
                .write_gff(paths["gff/3_to_gff"] / "narwikhorlabu1.bic")
            )
        # mixed ndy/nim tests
        if False:
            if not False:
                #app.gff.batch.convert_gff_to_json(
                #    paths["gff/0_from_gff"],
                #    paths["gff/1_to_json"]
                #)
                convert_gff_to_nim_json(
                    paths["gff/0_from_gff"],
                    paths["gff/1_to_json"]
                )
            if not False:
                app.gff.batch.convert_json_to_ndugff(
                    paths["gff/1_to_json"],
                    paths["gff/2_to_ndugff"]
                )
            if not False:
                app.gff.batch.convert_ndugff_to_gff(
                    paths["gff/2_to_ndugff"],
                    paths["gff/3_to_gff"]
                )
                convert_gff_to_nim_json(
                    paths["gff/3_to_gff"],
                    paths["gff/5_to_json"]
                )
        # full ndugff tests
        if False:
            if not False:
                app.gff.batch.convert_gff_to_json(
                    paths["gff/0_from_gff"],
                    paths["gff/1_to_json"]
                )
            if not False:
                app.gff.batch.convert_json_to_ndugff(
                    paths["gff/1_to_json"],
                    paths["gff/2_to_ndugff"]
                )
            if not False:
                app.gff.batch.convert_ndugff_to_gff(
                    paths["gff/2_to_ndugff"],
                    paths["gff/3_to_gff"]
                )
            if not False:
                app.gff.batch.convert_gff_to_ndugff(
                    paths["gff/3_to_gff"],
                    paths["gff/4_to_ndugff"]
                )
            if not False:
                app.gff.batch.convert_ndugff_to_json(
                    paths["gff/4_to_ndugff"],
                    paths["gff/5_to_json"]
                )
            if not False:
                app.gff.batch.convert_json_to_gff(
                    paths["gff/5_to_json"],
                    paths["gff/6_to_gff"]
                )
        # erf tests
        if not False:
            if not False:
                app.erf.batch.extract_erf_to_folder(
                    paths["erf/0_from_erf"],
                    paths["erf/1_to_folder"]
                )
            if not False:
                app.erf.batch.create_erf_from_folder(
                    paths["erf/1_to_folder"],
                    paths["erf/2_to_erf"]
                )
            if not False:
                app.erf.batch.extract_erf_to_folder(
                    paths["erf/2_to_erf"],
                    paths["erf/3_to_folder"]
                )
            if not False:
                app.erf.batch.create_erf_from_folder(
                    paths["erf/3_to_folder"],
                    paths["erf/4_to_erf"],
                    arg_for_distribution=True
                )
        # keybif exporter
        if False:
            app.keybif.export_game_resources(None, paths["keybif"])

if __name__ == "__main__":
    main()
