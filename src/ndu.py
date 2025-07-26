# native
import sys
from pathlib import Path
from contextlib import contextmanager
import json
import textwrap
import base64
from types import SimpleNamespace
from zipfile import ZipFile, ZIP_LZMA

# third-party
import regex
import nwn
from nwn import key as keybif
from nwn import gff
from nwn import erf


class _Paths:
    FILE_EXTENSIONS = {
        "ndugff": ".ndugff",
        "json": ".json",
        "gff": [
            ".are", ".git", ".gic",
            ".bic",
            ".dlg",
            ".gff",
            ".gui",
            ".ifo", ".fac", ".jrl",
            ".itp",
            ".utc", ".utd", ".ute", ".uti", ".utm", ".utp", ".uts", ".utt", ".utw",
        ],
        "erf": [
            ".erf", ".hak", ".mod", ".nwm"
        ],
    }

    @classmethod
    def _is_file_of_type(
        cls,
        arg_path,
        arg_skip_exist,
        arg_target_type,
        arg_base_type=None,
        arg_is_folder=False,
    ):
        if not isinstance(arg_path, (Path, str)):
            return False
        fp = Path(arg_path)
        suffixes = fp.suffixes
        # Valid files have exactly one or two suffixes,
        # depending on whether they are native file formats
        # or have been converted to a text format from source,
        # with the new target_suffix appended to the original filename.
        if len(suffixes) == 2:
            target_suffix, base_suffix = suffixes[-1].lower(), suffixes[0].lower()
        elif len(suffixes) == 1:
            target_suffix, base_suffix = suffixes[0].lower(), None
        else:
            return False
        target_ext = cls.FILE_EXTENSIONS.get(arg_target_type)
        if isinstance(target_ext, str):
            if target_suffix != target_ext:
                return False
        elif isinstance(target_ext, list):
            if target_suffix not in target_ext:
                return False
        else:
            return False
        if arg_base_type and base_suffix:
            base_ext = cls.FILE_EXTENSIONS.get(arg_base_type)
            if isinstance(base_ext, str):
                if base_suffix != base_ext:
                    return False
            elif isinstance(base_ext, list):
                if base_suffix not in base_ext:
                    return False
            else:
                return False
        try:
            if arg_is_folder:
                return arg_skip_exist or fp.is_dir()
            return arg_skip_exist or fp.is_file()
        except (OSError, PermissionError):
            return False

    @classmethod
    def is_gff_file(cls, arg_path, arg_skip_exist=False):
        """Check if a path refers to a valid GFF file.

        A GFF file is identified by having one of the known GFF-related extensions
        (e.g. .utc, .utp, .are, etc.). If `arg_skip_exist` is False, the file must also exist.

        Args:
            arg_path: The file path to check.
            arg_skip_exist: If True, skip checking whether the file exists on disk.

        Returns:
            True if the path looks like a valid GFF file; otherwise, False.
        """
        return cls._is_file_of_type(arg_path, arg_skip_exist, "gff")

    @classmethod
    def is_ndugff_file(cls, arg_path, arg_skip_exist=False):
        """Check if a path refers to a valid .ndugff file converted from a GFF source.

        The file must have a `.ndugff` extension and a known GFF extension as the inner suffix
        (e.g. `foo.utc.ndugff`). If `arg_skip_exist` is False, the file must also exist.

        Args:
            arg_path: The file path to check.
            arg_skip_exist: If True, skip checking whether the file exists on disk.

        Returns:
            True if the path looks like a valid NDU GFF file; otherwise, False.
        """
        return cls._is_file_of_type(arg_path, arg_skip_exist, "ndugff", "gff")

    @classmethod
    def is_json_file(cls, arg_path, arg_skip_exist=False):
        """Check if a path refers to a valid .json file converted from a GFF source.

        The file must have a `.json` extension and a known GFF extension as the inner suffix
        (e.g. `foo.utc.json`). If `arg_skip_exist` is False, the file must also exist.

        Args:
            arg_path: The file path to check.
            arg_skip_exist: If True, skip checking whether the file exists on disk.

        Returns:
            True if the path looks like a valid JSON representation of a GFF file; otherwise, False.
        """
        return cls._is_file_of_type(arg_path, arg_skip_exist, "json", "gff")

    @classmethod
    def is_erf_file(cls, arg_path, arg_skip_exist=False):
        """Check if a path refers to a valid ERF-format archive file.

        Accepts files with `.erf`, `.hak`, `.mod`, or `.nwm` extensions. If `arg_skip_exist` is False,
        the file must also exist.

        Args:
            arg_path: The file path to check.
            arg_skip_exist: If True, skip checking whether the file exists on disk.

        Returns:
            True if the path looks like a valid ERF archive file; otherwise, False.
        """
        return cls._is_file_of_type(arg_path, arg_skip_exist, "erf")

    @classmethod
    def is_erf_folder(cls, arg_path, arg_skip_exist=False):
        """Check if a path refers to a folder representing an extracted ERF archive.

        Intended for use with folders created by unpacking `.erf`, `.hak`, `.mod`, or `.nwm` files.
        If `arg_skip_exist` is False, the folder must also exist.

        Args:
            arg_path: The folder path to check.
            arg_skip_exist: If True, skip checking whether the folder exists on disk.

        Returns:
            True if the path looks like a valid ERF folder; otherwise, False.
        """
        return cls._is_file_of_type(arg_path, arg_skip_exist, "erf", arg_is_folder=True)

    @staticmethod
    def _resolve_script_path():
        if getattr(sys, 'frozen', False):
            # Handle PyInstaller, cx_Freeze or other frozen apps
            script_fp = Path(sys.executable).resolve()
        elif sys.argv and sys.argv[0]:
            script_fp = Path(sys.argv[0]).resolve()
        else:
            return None, None
        if script_fp.is_file():
            return script_fp.parent, script_fp.stem
        return None, None

    @staticmethod
    def _get_log_fp():
        script_dp, script_stem = _Paths._resolve_script_path()
        if script_dp and script_stem:
            return script_dp / f'{script_stem}.log'
        desktop_dp = Path.home() / "Desktop"
        desktop_dp.mkdir(parents=True, exist_ok=True)
        return desktop_dp / "ndu.log"

    @staticmethod
    def _get_default_data_dp():
        script_dp, script_stem = _Paths._resolve_script_path()
        if script_dp:
            data_dp = script_dp / script_stem
            data_dp.mkdir(parents=True, exist_ok=True)
            return data_dp
        return None

    @staticmethod
    def _get_dp(arg_path, arg_subfolder):
        if isinstance(arg_path, (str, Path)):
            dp = Path(arg_path).resolve()
            if dp.is_dir():
                # NOTE: if an existing path is passed to the function,
                # the assumption is that it is meant to be used directly,
                # without subfolders.
                return dp
        data_dp = _Paths._get_default_data_dp()
        if data_dp:
            dp = data_dp / arg_subfolder
            dp.mkdir(parents=True, exist_ok=True)
            if arg_path is not None:
                print(f'The provided {arg_path} path is invalid.\nDefaulting to "{dp}".')
            return dp
        return None

    @classmethod
    def _get_input_dp(cls, arg_path):
        return cls._get_dp(arg_path, "input")

    @classmethod
    def _get_output_dp(cls, arg_path):
        return cls._get_dp(arg_path, "output")

    @staticmethod
    def _get_nested_path_pairs(arg_input_root, arg_output_root, arg_validator, arg_output_namer):
        pairs = []
        input_dp = _Paths._get_input_dp(arg_input_root)
        output_dp = _Paths._get_output_dp(arg_output_root)
        if not input_dp or not output_dp:
            return pairs
        for input_fp in input_dp.rglob("*.*"):
            if not arg_validator(input_fp):
                continue
            relative_path = input_fp.parent.relative_to(input_dp)
            nested_output_dp = output_dp / relative_path
            nested_output_dp.mkdir(parents=True, exist_ok=True)
            output_fp = nested_output_dp / arg_output_namer(input_fp)
            pairs.append((input_fp, output_fp))
        return pairs

    @classmethod
    def _get_erf_path_pairs(cls, arg_input_root, arg_output_root, arg_extracting=True):
        pairs = []
        input_dp = _Paths._get_input_dp(arg_input_root)
        output_dp = _Paths._get_output_dp(arg_output_root)
        if not input_dp or not output_dp:
            return pairs
        if arg_extracting:
            for input_fp in input_dp.iterdir():
                if not cls.is_erf_file(input_fp):
                    continue
                extract_dp = output_dp / input_fp.name
                pairs.append((input_fp, extract_dp))
        else:
            for source_dp in input_dp.iterdir():
                if not cls.is_erf_folder(source_dp):
                    continue
                output_fp = output_dp / source_dp.name
                pairs.append((source_dp, output_fp))
        return pairs


class _Gff:
    class _Batch:
        def __init__(self):
            self._is_gff_file = _Paths.is_gff_file
            self._is_ndugff_file = _Paths.is_ndugff_file
            self._is_json_file = _Paths.is_json_file
            self._get_nested_path_pairs = _Paths._get_nested_path_pairs
            self._ndugff_ext = _Paths.FILE_EXTENSIONS["ndugff"]
            self._json_ext = _Paths.FILE_EXTENSIONS["json"]
            self._single = _Gff._Single()

        def convert_gff_to_json(self, arg_input_root=None, arg_output_root=None):
            """Convert all GFF files under a folder tree to JSON format.

            Recursively searches `arg_input_root` for GFF files and writes `.json` files
            to the corresponding location under `arg_output_root`, preserving the original
            GFF type as the inner extension (e.g., `foo.utc.json`).

            Args:
                arg_input_root: Root folder containing source GFF files.
                arg_output_root: Destination folder for generated JSON files.
            """
            input_validator = self._is_gff_file
            def output_namer(arg_input_fp): return f"{arg_input_fp.name}{self._json_ext}"
            fp_pairs = self._get_nested_path_pairs(
                arg_input_root, arg_output_root, input_validator, output_namer
            )
            for input_fp, output_fp in fp_pairs:
                self._single.load_gff(input_fp).write_json(output_fp)

        def convert_json_to_gff(self, arg_input_root=None, arg_output_root=None):
            """Convert all JSON files under a folder tree to native GFF format.

            Recursively searches `arg_input_root` for `.json` files representing GFF data,
            expecting the original GFF type as the inner extension (e.g., `foo.utc.json`),
            and writes binary GFF files to the corresponding location in `arg_output_root`.

            Args:
                arg_input_root: Root folder containing source JSON files.
                arg_output_root: Destination folder for generated GFF files.
            """
            input_validator = self._is_json_file
            def output_namer(arg_input_fp): return arg_input_fp.stem
            fp_pairs = self._get_nested_path_pairs(
                arg_input_root, arg_output_root, input_validator, output_namer
            )
            for input_fp, output_fp in fp_pairs:
                self._single.load_json(input_fp).write_gff(output_fp)

        def convert_gff_to_ndugff(self, arg_input_root=None, arg_output_root=None):
            """Convert all GFF files under a folder tree to NDU GFF text format.

            Recursively searches `arg_input_root` for GFF files and writes `.ndugff` text-format
            equivalents to the corresponding location in `arg_output_root`, preserving the original
            GFF type as the inner extension (e.g., `foo.utc.ndugff`).

            Args:
                arg_input_root: Root folder containing source GFF files.
                arg_output_root: Destination folder for generated NDU GFF files.
            """
            input_validator = self._is_gff_file
            def output_namer(arg_input_fp): return f"{arg_input_fp.name}{self._ndugff_ext}"
            fp_pairs = self._get_nested_path_pairs(
                arg_input_root, arg_output_root, input_validator, output_namer
            )
            for input_fp, output_fp in fp_pairs:
                self._single.load_gff(input_fp).write_ndugff(output_fp)

        def convert_ndugff_to_gff(self, arg_input_root=None, arg_output_root=None):
            """Convert all NDU GFF files under a folder tree back to binary GFF format.

            Recursively searches `arg_input_root` for `.ndugff` files, expecting the original GFF
            type as the inner extension (e.g., `foo.utc.ndugff`), and writes binary GFF files
            to the corresponding location in `arg_output_root`.

            Args:
                arg_input_root: Root folder containing `.ndugff` source files.
                arg_output_root: Destination folder for generated GFF files.
            """
            input_validator = self._is_ndugff_file
            def output_namer(arg_input_fp): return arg_input_fp.stem
            fp_pairs = self._get_nested_path_pairs(
                arg_input_root, arg_output_root, input_validator, output_namer
            )
            for input_fp, output_fp in fp_pairs:
                self._single.load_ndugff(input_fp).write_gff(output_fp)

        def convert_json_to_ndugff(self, arg_input_root=None, arg_output_root=None):
            """Convert all JSON GFF files under a folder tree to NDU GFF format.

            Recursively searches `arg_input_root` for `.json` files representing GFF data
            and writes `.ndugff` text-format files to `arg_output_root`, preserving the original
            GFF type as the inner extension (e.g., `foo.utc.ndugff`).

            The JSON format used is the same as that produced by the neverwinter.nim utilities.

            Args:
                arg_input_root: Root folder containing source JSON files.
                arg_output_root: Destination folder for generated NDU GFF files.
            """
            input_validator = self._is_json_file
            def output_namer(arg_input_fp): return f"{arg_input_fp.stem}{self._ndugff_ext}"
            fp_pairs = self._get_nested_path_pairs(
                arg_input_root, arg_output_root, input_validator, output_namer
            )
            for input_fp, output_fp in fp_pairs:
                self._single.load_json(input_fp).write_ndugff(output_fp)

        def convert_ndugff_to_json(self, arg_input_root=None, arg_output_root=None):
            """Convert all NDU GFF files under a folder tree to JSON format.

            Recursively searches `arg_input_root` for `.ndugff` files and writes the corresponding
            `.json` files to `arg_output_root`, preserving the original GFF type as the inner
            extension (e.g., `foo.utc.json`).

            The JSON format used is the same as that produced by the neverwinter.nim utilities.

            Args:
                arg_input_root: Root folder containing `.ndugff` source files.
                arg_output_root: Destination folder for generated JSON files.
            """
            input_validator = self._is_ndugff_file
            def output_namer(arg_input_fp): return f"{arg_input_fp.stem}{self._json_ext}"
            fp_pairs = self._get_nested_path_pairs(
                arg_input_root, arg_output_root, input_validator, output_namer
            )
            for input_fp, output_fp in fp_pairs:
                self._single.load_ndugff(input_fp).write_json(output_fp)

    class _Single:
        class _Dict(dict):
            def reorder(self, arg_field_types):
                def sort_key(arg_key):
                    type_index = list(arg_field_types).index(arg_key.type)
                    return (type_index, arg_key.name.lower())

                def sort_recursive(arg_node):
                    if type(arg_node) is dict:
                        sorted_items = sorted(arg_node.items(), key=lambda x: sort_key(x[0]))
                        return {k: sort_recursive(v) for k, v in sorted_items}
                    if type(arg_node) is list:
                        return [sort_recursive(e) for e in arg_node]
                    return arg_node

                return self.__class__(
                    sort_recursive(dict(self))
                )

        class _Field:
            class _Key:
                def __init__(self):
                    self.type = None
                    self.name = ""
                    self.id = None

            def __init__(self):
                self.reset()

            def reset(self):
                self.key = self._Key()
                self.value = None
                self.is_node = False
                self.constructor = None

        def __init__(self):
            self._ndugff_dict = None
            self._is_gff_file = _Paths.is_gff_file
            self._is_json_file = _Paths.is_json_file
            self._is_ndugff_file = _Paths.is_ndugff_file
            # NOTE: since the expected use is to have one instance of the class
            # to perform even batch conversions, the following constants are
            # assigned to the instance and not the class, for better consistency,
            # decluttering, formatting and ease of code folding.
            self._LANGUAGES = {
                0: "ENGLISH",
                1: "ENGLISH_F",
                2: "FRENCH",
                3: "FRENCH_F",
                4: "GERMAN",
                5: "GERMAN_F",
                6: "ITALIAN",
                7: "ITALIAN_F",
                8: "SPANISH",
                9: "SPANISH_F",
                10: "POLISH",
                11: "POLISH_F",
            }
            self._FIELD_TYPES = {
                "gff.Byte": {
                    "internal_value_type": int,
                    "gff_value_type": gff.Byte,
                    "dsl_type_name": "gff.Byte",
                    "json_type_name": "byte",
                },
                "gff.Char": {
                    "internal_value_type": int,
                    "gff_value_type": gff.Char,
                    "dsl_type_name": "gff.Char",
                    "json_type_name": "char",
                },
                "gff.Word": {
                    "internal_value_type": int,
                    "gff_value_type": gff.Word,
                    "dsl_type_name": "gff.Word",
                    "json_type_name": "word",
                },
                "gff.Short": {
                    "internal_value_type": int,
                    "gff_value_type": gff.Short,
                    "dsl_type_name": "gff.Short",
                    "json_type_name": "short",
                },
                "gff.Int": {
                    "internal_value_type": int,
                    "gff_value_type": gff.Int,
                    "dsl_type_name": "gff.Int",
                    "json_type_name": "int",
                },
                "gff.Dword": {
                    "internal_value_type": int,
                    "gff_value_type": gff.Dword,
                    "dsl_type_name": "gff.Dword",
                    "json_type_name": "dword",
                },
                "gff.Int64": {
                    "internal_value_type": int,
                    "gff_value_type": gff.Int64,
                    "dsl_type_name": "gff.Int64",
                    "json_type_name": "int64",
                },
                "gff.Dword64": {
                    "internal_value_type": int,
                    "gff_value_type": gff.Dword64,
                    "dsl_type_name": "gff.Dword64",
                    "json_type_name": "dword64",
                },
                "gff.Float": {
                    "internal_value_type": float,
                    "gff_value_type": gff.Float,
                    "dsl_type_name": "gff.Float",
                    "json_type_name": "float",
                },
                "gff.Double": {
                    "internal_value_type": float,
                    "gff_value_type": gff.Double,
                    "dsl_type_name": "gff.Double",
                    "json_type_name": "double",
                },
                "gff.MagicTag": {
                    "internal_value_type": str,
                    "gff_value_type": str,
                    "dsl_type_name": "gff.MagicTag",
                    "json_type_name": "__data_type",
                },
                "gff.ResRef": {
                    "internal_value_type": str,
                    "gff_value_type": gff.ResRef,
                    "dsl_type_name": "gff.ResRef",
                    "json_type_name": "resref",
                },
                "gff.CExoString": {
                    "internal_value_type": str,
                    "gff_value_type": gff.CExoString,
                    "dsl_type_name": "gff.CExoString",
                    "json_type_name": "cexostring",
                },
                "gff.Language": {
                    "internal_value_type": str,
                    "gff_value_type": nwn.GenderedLanguage,
                    "dsl_type_name": "gff.Language",
                    "json_type_name": None,
                },
                "gff.Base64String": {
                    "internal_value_type": str,
                    "gff_value_type": gff.VOID,
                    #"gff_value_type": bytes,
                    "dsl_type_name": "gff.Base64String",
                    "json_type_name": "void",
                },
                "gff.CExoLocString": {
                    "internal_value_type": dict,
                    "gff_value_type": gff.CExoLocString,
                    "dsl_type_name": "gff.CExoLocString",
                    "json_type_name": "cexolocstring",
                },
                "gff.Struct": {
                    "internal_value_type": dict,
                    "gff_value_type": gff.Struct,
                    "dsl_type_name": "gff.Struct",
                    "json_type_name": "struct",
                },
                "gff.List": {
                    "internal_value_type": list,
                    "gff_value_type": gff.List,
                    "dsl_type_name": "gff.List",
                    "json_type_name": "list",
                },
            }
            self._NODE_TYPES = {"gff.CExoLocString", "gff.Struct", "gff.List"}
            self._ESCAPED_STRING_TYPES = {"gff.CExoString", "gff.Language"}
            self._LITERAL_STRING_TYPES = {"gff.ResRef", "gff.MagicTag", "gff.Base64String"}
            self._GFF_UINT32_SENTINEL = 0xFFFFFFFF
            self._PRETTY_SENTINEL = -1
            self._DSL_TOKENIZER = regex.compile(
                fr'(?P<type>(?:{"|".join(self._FIELD_TYPES)}))'
                r"\((?P<name>[\w ]*)\)"
                r"(?:\.id\((?P<struct_id>-?\d+)\))?"
                r"(?:\:[ ]*(?P<value>.+)$)?"
            )

        def load_gff(self, arg_input_fp):
            """
            Load a `.gff` file from `arg_input_fp` and convert it
            into an internal dictionary for further processing.

            Args:
                arg_input_fp (Path or str): Path to the input `.gff` file.

            This method returns self and is chainable for concise load and write operations.

            Example:
                from ndu import App
                app = App()
                app.gff.single.load_gff('path/to/input/file.gff').write_ndugff('path/to/output/file.utc.ndugff')
            """
            def get_ndugff_language_name(arg_gff_language):
                lang = getattr(arg_gff_language, "lang", 0)
                gender = getattr(arg_gff_language, "gender", 0)
                language_id = lang * 2 + gender
                for k, v in self._LANGUAGES.items():
                    if k == language_id:
                        return v
                raise ValueError(f"Unknown GFF Language: {arg_gff_language}")

            def get_ndugff_value_type(arg_dsl_type):
                for v in self._FIELD_TYPES.values():
                    if arg_dsl_type == v["dsl_type_name"]:
                        return v["internal_value_type"]
                raise ValueError(f"Unknown DSL type: {arg_dsl_type}")

            def get_dsl_type(arg_gff_type):
                #if arg_gff_type is bytes:
                #    # TODO: Review this temporary hack
                #    arg_gff_type = gff.VOID
                for v in self._FIELD_TYPES.values():
                    if arg_gff_type == v["gff_value_type"]:
                        return v["dsl_type_name"]
                raise ValueError(f"Unknown GFF value type: {arg_gff_type}")

            def get_ndugff_key(arg_dsl_type, arg_name, arg_id=None):
                ndugff_key = self._Field._Key()
                ndugff_key.type = arg_dsl_type
                ndugff_key.name = arg_name
                if arg_dsl_type == "gff.Struct":
                    ndugff_key.id = arg_id if arg_id is not None else self._GFF_UINT32_SENTINEL
                return ndugff_key

            def get_ndugff_value(arg_dsl_type, arg_gff_value):
                if arg_dsl_type == "gff.Base64String":
                    return base64.b64encode(arg_gff_value).decode("ascii")
                if arg_dsl_type in self._ESCAPED_STRING_TYPES:
                    arg_gff_value = arg_gff_value.replace("\r\n", "\n").rstrip()
                ndugff_value_type = get_ndugff_value_type(arg_dsl_type)
                return ndugff_value_type(arg_gff_value)

            def get_ndugff_cexolocstring(arg_gff_value):
                d = dict()
                ndugff_key = get_ndugff_key("gff.Dword", "strref")
                ndugff_value = get_ndugff_value(
                    "gff.Dword",
                    getattr(arg_gff_value, "strref", self._GFF_UINT32_SENTINEL),
                )
                d.update({ndugff_key: ndugff_value})
                languages = getattr(arg_gff_value, "entries", dict())
                for gff_language, text in languages.items():
                    ndugff_key = get_ndugff_key("gff.Language", get_ndugff_language_name(gff_language))
                    ndugff_value = get_ndugff_value("gff.Language", text)
                    d.update({ndugff_key: ndugff_value})
                return d

            def get_ndugff_dict(arg_gff_struct):
                ndugff_dict = dict()
                for field_name, gff_value in arg_gff_struct.items():
                    gff_type = type(gff_value)
                    dsl_type = get_dsl_type(gff_type)
                    struct_id = getattr(gff_value, "struct_id", None)
                    ndugff_key = get_ndugff_key(dsl_type, field_name, struct_id)
                    if dsl_type == "gff.Struct":
                        ndugff_value = get_ndugff_dict(gff_value)
                    elif dsl_type == "gff.List":
                        ndugff_value = [get_ndugff_dict({"": c}) for c in gff_value]
                    elif dsl_type == "gff.CExoLocString":
                        ndugff_value = get_ndugff_cexolocstring(gff_value)
                    else:
                        ndugff_value = get_ndugff_value(dsl_type, gff_value)
                    ndugff_dict.update({ndugff_key: ndugff_value})
                return ndugff_dict

            # === Entry Point ===
            if self._is_gff_file(arg_input_fp):
                try:
                    with arg_input_fp.open("rb") as f:
                        root_struct, gff_root_type = gff.read(f)
                    self._ndugff_dict = self._Dict({
                        get_ndugff_key("gff.MagicTag", "__type__"): gff_root_type,
                        get_ndugff_key("gff.Struct", "__root__"): get_ndugff_dict(root_struct),
                    }).reorder(self._FIELD_TYPES)
                except ValueError:
                    print(f'Failed to process file: {arg_input_fp.name}')
            return self

        def load_json(self, arg_input_fp):
            """
            Load a `.json` file from `arg_input_fp` and convert it
            into an internal dictionary for further processing.

            Args:
                arg_input_fp (Path or str): Path to the input `.json` file.

            JSON filenames are expected to include the original GFF file type as an inner suffix,
            for example: `foo.utc.json`.
            See `app.gff.tools.is_json_file` for validation details.

            This method returns self and is chainable for concise load and write operations.

            Example:
                from ndu import App
                app = App()
                app.gff.single.load_json('path/to/input/file.json').write_gff('path/to/output/file.gff')
            """
            def log_and_raise(arg_message):
                print(
                    f'**INVALID DATA** --> {arg_message}\n'
                    f'in {arg_input_fp.name}'
                )
                raise ValueError

            def get_dsl_type(arg_json_type):
                for v in self._FIELD_TYPES.values():
                    if arg_json_type == v["json_type_name"]:
                        return v["dsl_type_name"]
                log_and_raise(f"Unknown JSON type: {arg_json_type}")

            def get_ndugff_value_type(arg_dsl_type):
                for v in self._FIELD_TYPES.values():
                    if arg_dsl_type == v["dsl_type_name"]:
                        return v["internal_value_type"]
                log_and_raise(f"Unknown DSL type: {arg_dsl_type}")

            def get_ndugff_language_name(arg_json_id):
                for k, v in self._LANGUAGES.items():
                    if k == int(arg_json_id):
                        return v
                log_and_raise(f"Unknown Language ID: {arg_json_id}")

            def get_unprettified_sentinel(arg_value):
                return (
                    self._GFF_UINT32_SENTINEL
                    if arg_value == self._PRETTY_SENTINEL
                    else arg_value
                )

            def get_ndugff_value(arg_dsl_type, arg_json_value):
                if arg_dsl_type in self._LITERAL_STRING_TYPES and "\\" in arg_json_value:
                    log_and_raise(
                        f"Backslashes are not allowed in {arg_dsl_type} "
                        f"literal strings: {arg_json_value!r}"
                    )
                if arg_dsl_type in self._ESCAPED_STRING_TYPES:
                    v = arg_json_value.replace(r"\r\n", r"\n").rstrip()
                elif arg_dsl_type == "gff.Dword":
                    v = get_unprettified_sentinel(arg_json_value)
                else:
                    v = arg_json_value
                value_converter = get_ndugff_value_type(arg_dsl_type)
                try:
                    return value_converter(v)
                except (ValueError, TypeError):
                    log_and_raise(f"Could not convert value {v!r} to {value_converter}")

            def get_ndugff_key(arg_dsl_type, arg_name, arg_field=None):
                ndugff_key = self._Field._Key()
                ndugff_key.type = arg_dsl_type
                ndugff_key.name = arg_name
                if arg_dsl_type == "gff.Struct" and type(arg_field) is dict:
                    json_id = arg_field.get("__struct_id", self._GFF_UINT32_SENTINEL)
                    ndugff_key.id = get_ndugff_value("gff.Dword", json_id)
                return ndugff_key

            def get_ndugff_cexolocstring(arg_json_value):
                d = dict()
                ndugff_key = get_ndugff_key("gff.Dword", "strref")
                strref = arg_json_value.pop("id", self._GFF_UINT32_SENTINEL)
                ndugff_value = get_ndugff_value("gff.Dword", strref)
                d.update({ndugff_key: ndugff_value})
                for language_id, text in arg_json_value.items():
                    ndugff_key = get_ndugff_key("gff.Language", get_ndugff_language_name(language_id))
                    ndugff_value = get_ndugff_value("gff.Language", text)
                    d.update({ndugff_key: ndugff_value})
                return d

            def validate_types(arg_dsl_type, arg_json_value):
                expected_type = None
                for v in self._FIELD_TYPES.values():
                    if v["dsl_type_name"] == arg_dsl_type:
                        expected_type = v["internal_value_type"]
                        break
                if expected_type is None:
                    log_and_raise(f"Unknown DSL type: {arg_dsl_type}")
                if type(arg_json_value) is expected_type:
                    return True
                log_and_raise(f"{arg_json_value!r} is not of the expected type {expected_type}")

            def get_ndugff_dict(arg_json_dict):
                ndugff_dict = dict()
                for field_name, json_field in arg_json_dict.items():
                    json_type = json_field.get("type")
                    dsl_type = get_dsl_type(json_type)
                    if dsl_type == "gff.Base64String":
                        # NOTE: this is a quirk of the json representation:
                        # the key name indicates the base64 encoding.
                        json_value = json_field.get("value64")
                    else:
                        json_value = json_field.get("value")
                    if validate_types(dsl_type, json_value):
                        if dsl_type == "gff.Struct":
                            ndugff_value = get_ndugff_dict(json_value)
                        elif dsl_type == "gff.CExoLocString":
                            ndugff_value = get_ndugff_cexolocstring(json_value)
                        elif dsl_type == "gff.List":
                            ndugff_value = [get_ndugff_dict(c) for c in json_value]
                        else:
                            ndugff_value = get_ndugff_value(dsl_type, json_value)
                        ndugff_key = get_ndugff_key(dsl_type, field_name, json_field)
                        ndugff_dict.update({ndugff_key: ndugff_value})
                return ndugff_dict

            def get_normalized_json_struct(arg_node, is_root=False):
                if is_root:
                    # Extract and remove the GFF data type
                    gff_type = arg_node.pop("__data_type", None)
                    if gff_type is None:
                        log_and_raise("Missing __data_type in root node")
                    # Inject struct wrapper for root
                    struct_node = {
                        "type": "struct",
                        "__struct_id": self._GFF_UINT32_SENTINEL,
                        "value": arg_node,
                    }
                    # Return full dict including type and root
                    return {
                        "__type__": {
                            "type": "__data_type",
                            "value": gff_type,
                        },
                        "__root__": get_normalized_json_struct(struct_node),
                    }
                node_type = arg_node.get("type")
                if not node_type:
                    log_and_raise("Field type not found")
                node_value = arg_node.get("value64") if node_type == "void" else arg_node.get("value")
                if node_value is None:
                    print(arg_node)
                    log_and_raise("Field value not found")
                if node_type == "list" and type(node_value) is not list:
                    log_and_raise("List value is not a list")
                if node_type == "struct" and type(node_value) is not dict:
                    log_and_raise("Struct value is not a dict")
                if node_type == "list":
                    new_list = list()
                    for e in node_value:
                        if type(e) is not dict:
                            log_and_raise("List child is not a struct")
                        struct_id = e.pop("__struct_id", None)
                        if struct_id is None:
                            log_and_raise("List struct is missing the struct_id")
                        # NOTE: It needs to be wrapped in a header with the missing metadata
                        new_list.append({
                            "": get_normalized_json_struct({
                                "type": "struct",
                                "__struct_id": struct_id,
                                "value": e,
                            }),
                        })
                    arg_node["value"] = new_list
                if node_type == "struct":
                    arg_node["value"].pop("__struct_id", None)
                    new_dict = dict()
                    for k, v in node_value.items():
                        new_dict.update({k: get_normalized_json_struct(v)})
                    arg_node["value"] = new_dict
                return arg_node

            def get_json_dict():
                with arg_input_fp.open(mode="r", encoding="utf-8") as f:
                    raw_dict = json.load(f)
                return get_normalized_json_struct(raw_dict, is_root=True)
                # NOTE: the root struct is missing the struct_id field,
                # which is necessary for processing downstream
                return {
                    # NOTE: extracting the GFF type, as it's stored as a field
                    # in the gff/json template
                    # TODO: merge this in using the is_node arg
                    "__type__": {
                        "type": "__data_type",
                        "value": raw_dict.pop("__data_type"),
                    },
                    "__root__": get_normalized_json_struct(
                        {
                            "type": "struct",
                            "__struct_id": self._GFF_UINT32_SENTINEL,
                            "value": raw_dict,
                        }
                    ),
                }

            # === Entry Point ===
            if self._is_json_file(arg_input_fp):
                try:
                    with arg_input_fp.open(mode="r", encoding="utf-8") as f:
                        raw_dict = json.load(f)
                    json_dict = get_normalized_json_struct(raw_dict, is_root=True)
                    self._ndugff_dict = self._Dict(
                        get_ndugff_dict(json_dict)
                    ).reorder(self._FIELD_TYPES)
                except ValueError:
                    pass
            return self

        def load_ndugff(self, arg_input_fp):
            """
            Load a `.ndugff` file from `arg_input_fp` and convert it
            into an internal dictionary for further processing.

            Args:
                arg_input_fp (Path or str): Path to the input `.ndugff` file.

            NDU GFF filenames are expected to include the original GFF file type as an inner suffix,
            for example: `foo.utc.ndugff`.
            See `app.gff.tools.is_ndugff_file` for validation details.

            This method returns self and is chainable for concise load and write operations.

            Example:
                from ndu import App
                app = App()
                app.gff.single.load_ndugff('path/to/input/file.ndugff').write_gff('path/to/output/file.gff')
            """
            class DslLine:
                def __init__(self):
                    self.reset()

                def reset(self):
                    self.nth = getattr(self, "nth", 0) + 1
                    self.raw = ""
                    self.type = None
                    self.name = ""
                    self.struct_id = None
                    self.value = None
                    self.is_node = False
                    self.is_node_end = False
                    self.skip = False

            dsl_line = DslLine()
            ndugff_field = self._Field()

            def log_and_raise(arg_message):
                print(
                    f'**INVALID DATA** --> {arg_message}\n'
                    f'in {arg_input_fp.name}, line #{dsl_line.nth}'
                )
                raise ValueError

            def normalize_magic_tag():
                dsl_line.value = dsl_line.value[:4].ljust(4)

            def unescape_escaped_string():
                dsl_line.value = (
                    dsl_line.value
                    .replace(r"\r\n", r"\n")
                    .replace(r'\"', '"')
                    .replace(r'\t', '\t')
                    .replace(r'\n', '\n')
                    .rstrip()
                )

            def unquote_quoted_string():
                dsl_line.value = dsl_line.value.strip('"')

            def get_unprettified_sentinel(arg_value):
                return (
                    str(self._GFF_UINT32_SENTINEL)
                    if arg_value == str(self._PRETTY_SENTINEL)
                    else arg_value
                )

            def set_constructor():
                for v in self._FIELD_TYPES.values():
                    if dsl_line.type == v["dsl_type_name"]:
                        ndugff_field.constructor = v["internal_value_type"]
                        return
                log_and_raise(f'Unknown value type {dsl_line.type}')

            def build_dsl_line(arg_line):
                if not arg_line or arg_line.startswith("#"):
                    dsl_line.skip = True
                    return
                if arg_line == "end()":
                    dsl_line.is_node_end = True
                    return
                match = self._DSL_TOKENIZER.match(arg_line)
                if not match:
                    log_and_raise(f"{arg_line!r}")
                tokens = match.groupdict()
                dsl_line.raw = arg_line
                dsl_line.type = tokens.get("type")
                dsl_line.name = tokens.get("name")
                dsl_line.struct_id = tokens.get("struct_id")
                dsl_line.value = tokens.get("value")
                if not dsl_line.type:
                    log_and_raise(f'{dsl_line.raw!r}')
                if dsl_line.type in self._NODE_TYPES:
                    dsl_line.is_node = True
                    if dsl_line.type == "gff.Struct":
                        if dsl_line.struct_id is None:
                            log_and_raise(f'{dsl_line.type} is missing its id')
                        dsl_line.struct_id = get_unprettified_sentinel(dsl_line.struct_id)
                else:
                    if not dsl_line.name:
                        log_and_raise(f'{dsl_line.type} is missing its field name')
                    if dsl_line.value is None:
                        log_and_raise(f'{dsl_line.type} is missing its value')
                    if type(dsl_line.value) is str:
                        unquote_quoted_string()
                        if "\\" in dsl_line.value:
                            if dsl_line.type in self._ESCAPED_STRING_TYPES:
                                unescape_escaped_string()
                            elif dsl_line.type in self._LITERAL_STRING_TYPES:
                                log_and_raise(f"Backslashes are not allowed in {dsl_line.type} strings")
                            else:
                                log_and_raise(f"Backslashes are not allowed in {dsl_line.type} values")
                        if dsl_line.type == "gff.MagicTag":
                            normalize_magic_tag()
                        if dsl_line.type == "gff.Dword":
                            dsl_line.value = get_unprettified_sentinel(dsl_line.value)

            def build_ndugff_field():
                ndugff_field.is_node = dsl_line.is_node
                ndugff_field.key.type = dsl_line.type
                ndugff_field.key.name = dsl_line.name
                if dsl_line.type == "gff.Struct":
                    try:
                        # NOTE: struct_ids seem to be gff.Dwords, given their boundaries.
                        # It isn't documented in the nwn.py library
                        ndugff_field.key.id = int(dsl_line.struct_id)
                    except (ValueError, TypeError):
                        log_and_raise(f"Could not convert id {dsl_line.struct_id!r} to gff.Dword")
                set_constructor()
                if ndugff_field.is_node:
                    ndugff_field.value = ndugff_field.constructor()
                else:
                    try:
                        ndugff_field.value = ndugff_field.constructor(dsl_line.value)
                    except (ValueError, TypeError):
                        log_and_raise(
                            f"Could not convert value {dsl_line.value!r} "
                            f"to {ndugff_field.constructor} for {dsl_line.type}"
                        )

            def build_ndugff_dict():
                with arg_input_fp.open(mode="r", encoding="utf-8") as f:
                    lines = [ln.strip() for ln in f.readlines()]
                stack = [{"root": dict()}]
                for line in lines:
                    build_dsl_line(line)
                    if dsl_line.skip:
                        continue
                    elif dsl_line.is_node_end:
                        if len(stack) <= 1:
                            log_and_raise("Unexpected end() without matching open node")
                        child = stack.pop()
                        parent = next(iter(stack[-1].values()))
                        if type(parent) is list:
                            parent.append(child)
                        else:
                            parent.update(child)
                    else:
                        build_ndugff_field()
                        if ndugff_field.is_node:
                            stack.append({ndugff_field.key: ndugff_field.value})
                        else:
                            target = next(iter(stack[-1].values()))
                            if type(target) is not dict:
                                log_and_raise("This field should be under a gff.Struct")
                            target.update({ndugff_field.key: ndugff_field.value})
                    dsl_line.reset()
                    ndugff_field.reset()
                self._ndugff_dict = self._Dict(
                    stack[0]["root"]
                ).reorder(self._FIELD_TYPES)

            # === Entry Point ===
            if self._is_ndugff_file(arg_input_fp):
                try:
                    build_ndugff_dict()
                except ValueError:
                    pass
            return self

        def write_gff(self, arg_output_fp):
            """
            Write the currently loaded data to a binary `.gff` file at `arg_output_fp`.

            Args:
                arg_output_fp (Path or str): Path to the output `.gff` file.

            This method returns self and is chainable for concise load and write operations.

            Example:
                from ndu import App
                app = App()
                app.gff.single.load_ndugff('path/to/input/file.ndugff').write_gff('path/to/output/file.gff')
            """
            def get_gff_value_type(arg_dsl_type):
                for v in self._FIELD_TYPES.values():
                    if arg_dsl_type == v["dsl_type_name"]:
                        return v["gff_value_type"]
                raise ValueError(f"Unknown DSL type: {arg_dsl_type}")

            def get_gff_language(arg_name):
                for language_id, name in self._LANGUAGES.items():
                    if name == arg_name:
                        return nwn.GenderedLanguage.from_id(language_id)
                raise ValueError(f"Unknown Language Name: {arg_name}")

            def get_gff_cexolocstring(arg_ndugff_value):
                strref = gff.Dword(self._GFF_UINT32_SENTINEL)
                entries = dict()
                for ndugff_key, ndugff_value in arg_ndugff_value.items():
                    gff_value_type = get_gff_value_type(ndugff_key.type)
                    if gff_value_type is gff.Dword and ndugff_key.name == "strref":
                        strref = int(ndugff_value)
                        strref = get_gff_value(ndugff_key, ndugff_value)
                    elif gff_value_type is nwn.GenderedLanguage:
                        entries.update({get_gff_language(ndugff_key.name): ndugff_value})
                return gff.CExoLocString(strref, entries)

            def get_gff_value(arg_ndugff_key, arg_ndugff_value):
                converter = get_gff_value_type(arg_ndugff_key.type)
                if converter is gff.VOID:
                    return gff.VOID(base64.b64decode(arg_ndugff_value.encode("ascii")))
                return converter(arg_ndugff_value)

            def get_gff_struct(arg_ndugff_key, arg_ndugff_dict):
                gff_struct = gff.Struct(arg_ndugff_key.id)
                for ndugff_key, ndugff_value in arg_ndugff_dict.items():
                    if ndugff_key.type == "gff.Struct":
                        gff_value = get_gff_struct(ndugff_key, ndugff_value)
                    elif ndugff_key.type == "gff.List":
                        gff_value = gff.List()
                        for child in ndugff_value:
                            for k, v in child.items():
                                gff_value.append(get_gff_struct(k, v))
                    elif ndugff_key.type == "gff.CExoLocString":
                        gff_value = get_gff_cexolocstring(ndugff_value)
                    else:
                        gff_value = get_gff_value(ndugff_key, ndugff_value)
                    gff_struct.update({ndugff_key.name: gff_value})
                return gff_struct

            def get_gff_data():
                gff_root = None
                gff_type = None
                for ndugff_key, ndugff_value in self._ndugff_dict.items():
                    if ndugff_key.name == "__root__":
                        gff_root = get_gff_struct(ndugff_key, ndugff_value)
                    elif ndugff_key.name == "__type__":
                        gff_type = get_gff_value(ndugff_key, ndugff_value)
                return gff_root, gff_type

            # === Entry Point ===
            if self._is_gff_file(arg_output_fp, arg_skip_exist=True) and self._ndugff_dict:
                arg_output_fp.parent.mkdir(parents=True, exist_ok=True)
                gff_root, gff_type = get_gff_data()
                with arg_output_fp.open("wb") as f:
                    gff.write(f, gff_root, gff_type)
            return self

        def write_json(self, arg_output_fp):
            """
            Write the currently loaded data to a `.json` file at `arg_output_fp`.

            Args:
                arg_output_fp (Path or str): Path to the output `.json` file.

            JSON filenames are expected to include the original GFF file type as an inner suffix,
            for example: `foo.utc.json`.
            See `app.gff.tools.is_json_file` for validation details.

            This method returns self and is chainable for concise load and write operations.

            Example:
                from ndu import App
                app = App()
                app.gff.single.load_gff('path/to/input/file.gff').write_json('path/to/output/file.json')
            """
            def get_json_type(arg_dsl_type):
                for v in self._FIELD_TYPES.values():
                    if arg_dsl_type == v["dsl_type_name"]:
                        return v["json_type_name"]
                raise ValueError(f"Unknown DSL type: {arg_dsl_type}")

            def get_json_language_id(arg_name):
                for k, v in self._LANGUAGES.items():
                    if v == arg_name:
                        return str(k)
                raise ValueError(f"Unknown Language Name: {arg_name}")

            def get_json_cexolocstring(arg_ndugff_value):
                d = dict()
                for ndugff_key, ndugff_value in arg_ndugff_value.items():
                    if ndugff_key.type == "gff.Dword" and ndugff_key.name == "strref" and ndugff_value != self._GFF_UINT32_SENTINEL:
                        # NOTE: the id/strref field seems to be optional in the
                        # json template, and only present when not set to the sentinel value
                        d.update({"id": ndugff_value})
                    elif ndugff_key.type == "gff.Language":
                        d.update({get_json_language_id(ndugff_key.name): ndugff_value})
                return d

            def get_json_dict(arg_ndugff_dict):
                json_dict = dict()
                for ndugff_key, ndugff_value in arg_ndugff_dict.items():
                    json_type = get_json_type(ndugff_key.type)
                    if json_type == "__data_type":
                        # NOTE: in the json representation,
                        # the GFF subtype is stored as a root field
                        json_dict.update({json_type: ndugff_value})
                        continue
                    json_field = {ndugff_key.name: {"type": json_type}}
                    if ndugff_key.type == "gff.Struct":
                        struct_id_field = {"__struct_id": ndugff_key.id}
                        if ndugff_key.name in ("__root__", ""):
                            # NOTE: root and nameless structs
                            # do not use the normal/named struct template.
                            # The json_field value overrides the whole json_field.
                            # NOTE: a nameless struct is a list member.
                            # Unlike the root struct, it requires the
                            # struct_id as the first child.
                            json_field = struct_id_field if ndugff_key.name == "" else dict()
                            json_field.update(get_json_dict(ndugff_value))
                        else:
                            # NOTE: the json representation of
                            # a named struct requires the struct_id
                            # as both a metadata property and as a
                            # value property.
                            json_field[ndugff_key.name].update(struct_id_field)
                            json_field[ndugff_key.name].update({"value": struct_id_field | get_json_dict(ndugff_value)})
                    elif ndugff_key.type == "gff.List":
                        json_field[ndugff_key.name].update({"value": [get_json_dict(c) for c in ndugff_value]})
                    elif ndugff_key.type == "gff.CExoLocString":
                        json_field[ndugff_key.name].update({"value": get_json_cexolocstring(ndugff_value)})
                    elif ndugff_key.type == "gff.Base64String":
                        # NOTE: this is a quirk of the json representation:
                        # the key name indicates the base64 encoding.
                        json_field[ndugff_key.name].update({"value64": ndugff_value})
                    else:
                        json_field[ndugff_key.name].update({"value": ndugff_value})
                    json_dict.update(json_field)
                return json_dict

            # === Entry Point ===
            if self._is_json_file(arg_output_fp, arg_skip_exist=True) and self._ndugff_dict:
                arg_output_fp.parent.mkdir(parents=True, exist_ok=True)
                json_dict = get_json_dict(self._ndugff_dict)
                with arg_output_fp.open(mode="w", encoding="utf-8") as f:
                    json.dump(json_dict, f, indent=4, ensure_ascii=False)
            return self

        def write_ndugff(self, arg_output_fp):
            """
            Write the currently loaded data to a `.ndugff` file at `arg_output_fp`.

            Args:
                arg_output_fp (Path or str): Path to the output `.ndugff` file.

            NDU GFF filenames are expected to include the original GFF file type as an inner suffix,
            for example: `foo.utc.ndugff`.
            See `app.gff.tools.is_ndugff_file` for validation details.

            This method returns self and is chainable for concise load and write operations.

            Example:
                from ndu import App
                app = App()
                app.gff.single.load_gff('path/to/input/file.gff').write_ndugff('path/to/output/file.ndugff')
            """
            ndugff_field = self._Field()
            dsl_lines = list()

            def get_escaped_string():
                return (
                    ndugff_field.value
                    .replace("\"", r"\"")
                    .replace("\t", r"\t")
                    .replace("\r\n", r"\n")
                    .replace("\n", r"\n")
                )

            def get_pretty_sentinel(arg_value):
                return self._PRETTY_SENTINEL if arg_value == self._GFF_UINT32_SENTINEL else arg_value

            def get_indent(arg_depth):
                return " " * int(4 * arg_depth)

            def get_formatted_key():
                if ndugff_field.key.type == "gff.Struct":
                    return (
                        f'{ndugff_field.key.type}'
                        f'({ndugff_field.key.name})'
                        f'.id({get_pretty_sentinel(ndugff_field.key.id)})'
                    )
                return f"{ndugff_field.key.type}({ndugff_field.key.name})"

            def get_formatted_value():
                if ndugff_field.key.type in self._ESCAPED_STRING_TYPES:
                    v = get_escaped_string()
                elif ndugff_field.key.type == "gff.Dword":
                    v = get_pretty_sentinel(ndugff_field.value)
                else:
                    v = ndugff_field.value
                if ndugff_field.key.type in self._ESCAPED_STRING_TYPES | self._LITERAL_STRING_TYPES:
                    v = f'"{v}"'
                return f': {v}'

            def end_node(arg_depth):
                # Indent `end()` midway between levels to visually separate it from fields.
                # This helps code folding UIs collapse the block correctly while preventing
                # `end()` from appearing aligned with child fields.
                dsl_lines.append(f'{get_indent(arg_depth + 0.5)}end()')

            def dump_field_line(arg_depth):
                field_line = get_indent(arg_depth) + get_formatted_key()
                if ndugff_field.key.type not in self._NODE_TYPES:
                    field_line += get_formatted_value()
                dsl_lines.append(field_line)

            def dump_dict_lines(arg_ndugff_dict, arg_depth=0):
                for ndugff_key, ndugff_value in arg_ndugff_dict.items():
                    ndugff_field.key = ndugff_key
                    ndugff_field.value = ndugff_value
                    dump_field_line(arg_depth)
                    if type(ndugff_value) is dict:
                        dump_dict_lines(ndugff_value, arg_depth + 1)
                        end_node(arg_depth)
                    elif type(ndugff_value) is list:
                        for v in ndugff_value:
                            dump_dict_lines(v, arg_depth + 1)
                        end_node(arg_depth)
                    # NOTE: redundant, but more explicit and possibly clearer?
                    ndugff_field.reset()

            # === Entry Point ===
            if self._is_ndugff_file(arg_output_fp, arg_skip_exist=True) and self._ndugff_dict:
                arg_output_fp.parent.mkdir(parents=True, exist_ok=True)
                dump_dict_lines(self._ndugff_dict)
                with arg_output_fp.open(mode="w", encoding="utf-8") as f:
                    f.write("\n".join(dsl_lines))
            return self


class _Erf:
    # TODO: Use regex validation for the resource names. Consider that erf content
    # could have been named in very unconventional ways. That'll need to be handled somehow.
    class _Batch:
        def __init__(self):
            self._single = _Erf._Single()
            self._package_fp = None
            self._erf_fps = []

        def extract_erf_to_folder(self, arg_input_root=None, arg_output_root=None):
            """
            Extract the contents of all ERF-like archives in a directory to corresponding folders.

            Args:
                arg_input_root (Path or str, optional): Directory containing `.erf`, `.mod`, `.hak`, or `.nvm` files.
                arg_output_root (Path or str, optional): Directory where output folders will be created.

            Only immediate children of `arg_input_root` are processed. This avoids ambiguity
            in distinguishing user-organized subfolders from ERF source files.

            Each archive is extracted to a folder named after the file (including extension).
            See `app.erf.tools.is_erf_file` for input file validation details.
            """
            path_pairs = _Paths._get_erf_path_pairs(arg_input_root, arg_output_root)
            for input_fp, output_dp in path_pairs:
                self._single.extract_erf_to_folder(input_fp, output_dp)

        def create_erf_from_folder(self, arg_input_root=None, arg_output_root=None, arg_for_distribution=False):
            """
            Create ERF-like archives from folders located in a root directory.

            Args:
                arg_input_root (Path or str, optional): Directory containing folders to convert into ERF archives.
                arg_output_root (Path or str, optional): Directory where output archives will be written.
                arg_for_distribution (bool): If True, all output archives are also bundled into a ZIP package.

            Only immediate children of `arg_input_root` are processed. This avoids ambiguity
            in distinguishing user-organized subfolders from archive sources.

            Each folder must be named after the archive it represents, including the file extension.
            See `app.erf.tools.is_erf_folder` for input folder validation details.
            """
            path_pairs = _Paths._get_erf_path_pairs(arg_input_root, arg_output_root, False)
            for input_dp, output_fp in path_pairs:
                self._single.create_erf_from_folder(input_dp, output_fp)
                if arg_for_distribution:
                    if self._package_fp is None:
                        self._package_fp = output_fp.parent / "_distribution/package.zip"
                    self._erf_fps.append(output_fp)
            if arg_for_distribution and self._package_fp and self._erf_fps:
                self._package_fp.parent.mkdir(parents=True, exist_ok=True)
                with ZipFile(self._package_fp, mode="w", compression=ZIP_LZMA) as zipf:
                    for fp in self._erf_fps:
                        zipf.write(fp, arcname=fp.name)
                self._package_fp = None
                self._erf_fps = []

    class _Single:
        _ERF_TYPES = {
            ".erf": b"ERF ",
            ".mod": b"MOD ",
            ".hak": b"HAK ",
            ".nvm": b"NVM ",
        }

        def _get_erf_type_by_extension(self, arg_ext):
            erf_type = self._ERF_TYPES.get(arg_ext.lower())
            if erf_type is None:
                print(
                    f'"{arg_ext}" is not a recognized file extension. '
                    'Falling back to the default file type (ERF).'
                )
            return erf_type or b"ERF"

        def extract_erf_to_folder(self, arg_input_fp, arg_output_dp):
            """
            Extract the contents of an ERF-like archive to the specified output folder.

            Args:
                arg_input_fp (Path or str): Path to the input `.erf`, `.mod`, `.hak`, or `.nvm` file.
                arg_output_dp (Path or str): Path to the output folder where contents will be extracted.

            The archive contents will be written into the specified folder.
            See `app.erf.tools.is_erf_file` for input file validation details.
            """
            if _Paths.is_erf_file(arg_input_fp):
                arg_output_dp.mkdir(parents=True, exist_ok=True)
                with arg_input_fp.open(mode="rb") as input_f:
                    reader = erf.Reader(input_f)
                    for filename in reader.filenames:
                        with (arg_output_dp / filename).open("wb") as output_f:
                            output_f.write(
                                reader.read_file(filename)
                            )

        def create_erf_from_folder(self, arg_input_dp, arg_output_fp):
            """
            Create an ERF-like archive from the contents of a folder.

            Args:
                arg_input_dp (Path or str): Path to the input folder containing files to be archived.
                arg_output_fp (Path or str): Path to the output `.erf`, `.mod`, `.hak`, or `.nvm` file.

            The input folder must be named after the desired archive, including the extension.
            See `app.erf.tools.is_erf_folder` for input folder validation details.
            """
            if _Paths.is_erf_folder(arg_input_dp):
                with arg_output_fp.open(mode="wb") as output_f:
                    erf_type = self._get_erf_type_by_extension(arg_output_fp.suffix)
                    with erf.Writer(output_f, file_type=erf_type) as writer:
                        for fp in arg_input_dp.glob("*.*"):
                            with fp.open(mode="rb") as input_f:
                                # NOTE: Bug upstream currently prevents
                                # passing the file object directly,
                                # as it fails to extract the bytes itself
                                writer.add_file(fp.name, input_f.read())


class _KeyBif:
    def __init__(self):
        self._input_structure = {
            "selected": {
                "properties":["source_id", "recipe_id"],
                "children": []
            },
            "source": {
                "properties":["id", "description"],
                "children": ["game"]
            },
            "recipe": {
                "properties":["id", "description"],
                "children": ["match", "exclude"]
            },
            "game": {
                "properties":["path", "keylist"],
                "children": []
            },
            "match": {
                "properties":["fullname", "name_start", "name_part", "name_end", "extension"],
                "children": []
            },
            "exclude": {
                "properties":["fullname", "name_start", "name_part", "name_end", "extension"],
                "children": []
            },
        }
        self._input_tokenizer = self._get_input_tokenizer()
        self._value_tokenizer = self._get_value_tokenizer()
        self._default_recipes = self._get_default_recipes()

    def _get_input_tokenizer(self):
        props = list(dict.fromkeys(p for v in self._input_structure.values() for p in v["properties"]))
        return regex.compile(
            fr'^(?P<type>{"|".join(self._input_structure)})'
            fr'|(?:\.(?P<property>{"|".join(props)})\((?P<value>"[^"]+"|\d+)\))'
        )

    def _get_value_tokenizer(self):
        return regex.compile(r"[,\s|;\'\"]+")

    def _get_default_recipes(self):
        return textwrap.dedent(r"""
            ### === KEYBIF EXTRACTOR CONFIGURATION ===
                This file defines which files should be included or excluded
                when extracting game resources.

                You can define sources (game installs) and recipes (filters),
                and store them for easy reuse. Once defined, simply select one
                source and one recipe to apply at a time.
            ###

            ### === ACTIVE SELECTION ===
                Only one source and one recipe are used at a time.
            ###
            selected.source_id(0).recipe_id(0)

            ### === SOURCES ===
                Define one or more game installs here. Useful for switching
                between stable, beta, or preview versions.

                To create a new source:
                    1. Copy an existing source block.
                    2. Assign it a new unique ID.
                    3. Set the path to your game installation.
                    4. Optionally specify a list of key files, or leave it empty to use the default.
                    By default, it will load:
                        - nwn_retail.key (latest overrides)
                        - nwn_base.key   (base game)
                    This covers most needs — you usually don’t need to change it.
            ###
            source.id(0).description("Stable")
                game.path("/my/games/steam/steamapps/common/Neverwinter Nights")
                game.keylist("nwn_retail, nwn_base")

            ### === RECIPES ===
                Define filters that select which files to extract.

                To create a new recipe:
                    1. Copy an existing recipe block.
                    2. Assign it a new unique ID.
                    3. Add match and exclude lines as needed.

                Filter fields:
                    name_start("text")   → matches if filename starts with "text"
                    name_part("text")    → matches if filename contains "text"
                    name_end("text")     → matches if filename ends with "text"
                    extension("ext")     → matches the file extension (e.g. "mdl")

                Wildcards allowed inside quotes:
                    @ → any letter         (e.g. "pm@" matches "pma", "pmb")
                    # → any digit          (e.g. "file#" matches "file1", "file9")
                    ? → letter/digit/_     (like \w in regex; matches "a", "3", "_", etc.)

                Rule priority (in order):
                    1. exclude.fullname() → Blacklist: always excluded
                    2. match.fullname()   → Whitelist: always included (unless blacklisted above)
                    3. exclude[...]       → Pattern-based exclusion (e.g. by name or extension)
                    4. match[...]         → Pattern-based inclusion (OR logic)

                    If a file matches multiple filters, this order decides which one "wins".
                    A file blacklisted by `exclude.fullname()` is never included, even if other rules match.
                    A file whitelisted by `match.fullname()` is always included, unless blacklisted first.
            ###
            recipe.id(0).description("Template")
                ### Copy this block to define a new recipe.
                    Fill in one or more values per line.
                    Empty lines can be deleted if unused.
                ###
                exclude.fullname()
                match.fullname()
                exclude.name_start().name_part().name_end().extension()
                match.name_start().name_part().name_end().extension()

            ### === EXAMPLE RECIPES === ###

            recipe.id(1000).description("All GFF files")
                # A list of extensions
                match.extension("are, git, gic, bic, dlg, fac, gff, gui, ifo, itp, jrl")
                match.extension("ut@")

            recipe.id(1001).description("All 2DA files except tileset-related")
                exclude.name_end("_edge").extension("2da")
                exclude.name_part("door").extension("2da")
                match.extension("2da")

            recipe.id(1002).description("Tileset control files")
                match.name_end("_edge").extension("2da")
                match.extension("set")

            recipe.id(1003).description("GUI-related files")
                match.fullname("dth_deathopts.mdl, editsvrstat.mdl, empty.mdl, gui_empty.mdl")
                match.extension("gui")
                match.name_start("gui").extension("mdl, tga, dds, plt")
                match.name_start("ctl_, edit_, inv_, pnl_").extension("mdl")

            recipe.id(1004).description("Part-based models")
                match.name_start("pm@#_@, pf@###_@").name_part().extension("mdl, plt")
                match.name_start("ipm_, ipf_").name_part().extension("plt")
        """).lstrip("\n")

    def export_game_resources(self, arg_recipes=None, arg_output=None):
        """
        Extract game resources based on a selected recipe configuration.

        Args:
            arg_recipes (str or Path, optional): Path to the `.recipes` configuration file.
                If not provided, attempts to locate a default `.recipes` file relative to the
                running script.
            arg_output (str or Path, optional): Directory where extracted files will be saved.

        The method applies include and exclude filters defined in the recipe to select files
        for extraction from the `.key/bif` archives. Filtering supports simple wildcards and
        follows a priority order to resolve conflicts.
        A detailed explanation of the recipes' logic can be found inside the .recipe config file itself.
        """
        def _is_match_by_patterns(arg_filename, arg_patterns):
            if not arg_patterns:
                return False
            stem = Path(arg_filename).stem
            ext = Path(arg_filename).suffix.lstrip(".")
            for group in arg_patterns:
                if not any(group.get(k) for k in ("name_start", "name_end", "name_part", "extension")):
                    continue
                if group.get("name_start") and not any(p.match(stem) for p in group["name_start"]):
                    continue
                if group.get("name_end") and not any(p.search(stem) for p in group["name_end"]):
                    continue
                if group.get("name_part") and not any(p.search(stem) for p in group["name_part"]):
                    continue
                if group.get("extension") and not any(p.search(ext) for p in group["extension"]):
                    continue
                return True
            return False

        def _is_match(arg_filename, arg_filters):
            if arg_filename in arg_filters["exclude_filenames"] or []:
                return False
            if arg_filename in arg_filters["include_filenames"] or []:
                return True
            if _is_match_by_patterns(arg_filename, arg_filters["exclude_patterns"]):
                return False
            if _is_match_by_patterns(arg_filename, arg_filters["include_patterns"]):
                return True
            return False

        output_dp = _Paths._get_output_dp(arg_output)
        input_data = self._InputResolver(self, arg_recipes)._resolve()
        recipe = self._RecipeCompiler(self, input_data)._compile()
        if output_dp and recipe:
            for key_name, key_fp in recipe["keys"].items():
                key_output_dp = output_dp / f'recipe_{recipe["id"]}' / key_name
                key_output_dp.mkdir(parents=True, exist_ok=True)
                with keybif.Reader(str(key_fp)) as rd:
                    for resource in rd.filenames():
                        filename = resource.lower()
                        if _is_match(filename, recipe["filters"]):
                            with open(key_output_dp / filename, mode="wb") as f:
                                f.write(rd.read_file(resource))

    def write_default_recipes(self, arg_output=None):
        """
        Writes the default recipes configuration to a file in the default data directory.

        Args:
            arg_output (Path or str): Optional override for the output directory.

        Returns:
            Path: Path to the written file.
        """
        recipes_fp = _Paths._get_output_dp(arg_output) / "ndu_keybif.recipes"
        recipes_fp.write_text(self._default_recipes, encoding="utf-8")
        print(f'Default recipes generated as: {recipes_fp}')
        return recipes_fp

    class _InputResolver:
        def __init__(self, outer, arg_recipes):
            self._structure = outer._input_structure
            self._tokenizer = outer._input_tokenizer
            self._default_recipes = outer._default_recipes
            self._input_fp = self._resolve_fp(arg_recipes)

        def _resolve_fp(self, arg_recipes):
            fp = Path(arg_recipes) if isinstance(arg_recipes, (str, Path)) else None
            if fp and fp.is_file() and fp.suffix == ".recipes":
                return fp
            script_dp, script_stem = _Paths._resolve_script_path()
            if script_dp:
                fp = script_dp / f'{script_stem}.recipes'
                if not fp.is_file():
                    fp.write_text(self._default_recipes, encoding="utf-8")
                return fp
            return None

        def _get_tokenized_input(self):
            def split_outside_quotes(arg_line, arg_delimiter):
                tokens = []
                current = ""
                i = 0
                in_quote = False
                while i < len(arg_line):
                    if not in_quote and arg_line.startswith(arg_delimiter, i):
                        tokens.append(current)
                        current = ""
                        i += len(arg_delimiter)
                        tokens.append(arg_delimiter)
                    else:
                        if arg_line[i] == '"':
                            in_quote = not in_quote
                        current += arg_line[i]
                        i += 1
                tokens.append(current)
                return [t.strip() for t in tokens if t]

            def strip_comments(arg_lines):
                lines = []
                in_block = False
                for line in arg_lines:
                    if line == "":
                        continue
                    tokens = split_outside_quotes(line, "###")
                    if "###" in tokens:
                        for t in tokens:
                            if t == "###":
                                in_block = not in_block
                            else:
                                if not in_block:
                                    lines.append(t)
                        continue
                    if in_block:
                        continue
                    tokens = split_outside_quotes(line, "#")
                    if "#" in tokens:
                        for t in tokens:
                            if t == "#":
                                break
                            else:
                                lines.append(t)
                        continue
                    lines.append(line)
                return lines

            input_tokens = list()
            with self._input_fp.open() as f:
                lines = strip_comments([line.strip() for line in f.readlines()])
            for line in lines:
                line_tokens = dict()
                for match in self._tokenizer.finditer(line):
                    if match.group('type'):
                        line_tokens['type'] = match.group('type')
                    elif match.group('property') and match.group('value'):
                        line_tokens[match.group('property')] = match.group('value').strip('"')
                if "type" in line_tokens and len(line_tokens) > 1:
                    input_tokens.append(line_tokens)
            return input_tokens

        def _get_structured_input(self, tokens):
            def merge_node(arg_node, arg_dict):
                plurals = {
                    "source": "sources",
                    "recipe": "recipes",
                }
                node_type = arg_node.pop("type", None)
                node_id = arg_node.pop("id", None)
                if node_type and node_id:
                    arg_dict[plurals[node_type]][node_id] = arg_node

            data = {
                "source_id": None,
                "recipe_id": None,
                "sources": dict(),
                "recipes": dict(),
            }
            current_node = dict()
            for token in tokens:
                token_type = token.pop("type")
                if token_type == "selected":
                    for id_type in ["source_id", "recipe_id"]:
                        if id_type in token:
                            data[id_type] = int(token[id_type])
                elif token_type in ["source", "recipe"]:
                    merge_node(current_node, data)
                    current_node = {
                        "type": token_type,
                        "id": int(token.get("id", -1)),
                        "description": token.get("description", ""),
                    }
                    for child in self._structure[token_type]["children"]:
                        current_node[child] = list()
                elif token_type in self._structure[current_node["type"]]["children"]:
                    if token_type == "game":
                        if current_node.get(token_type):
                            current_node[token_type].update(token)
                        else:
                            current_node[token_type] = token
                    else:
                        current_node[token_type].append(token)
            merge_node(current_node, data)
            return (
                data["recipe_id"],
                data["sources"][data["source_id"]].get("game", dict()),
                data["recipes"].get(data["recipe_id"], dict())
            )

        def _resolve(self):
            tokens = self._get_tokenized_input()
            return self._get_structured_input(tokens)

    class _RecipeCompiler:
        def __init__(self, outer, arg_data):
            self._tokenizer = outer._value_tokenizer
            self._data = arg_data

        def _compile(self):
            def resolve_token_wildcards(arg_token):
                return (
                    arg_token.lower()
                    .replace("?", r"\w")
                    .replace("#", r"[0-9]")
                    .replace("@", r"[a-z]")
                )

            def get_value_tokens(arg_value):
                tokens = []
                for t in self._tokenizer.split(arg_value):
                    resolved = resolve_token_wildcards(t)
                    if resolved and resolved not in tokens:
                        tokens.append(resolved)
                return tokens

            def compile_patterns(arg_group):
                for k in arg_group:
                    values = arg_group[k]
                    if k == "name_start":
                        arg_group[k] = [regex.compile(fr"^{p}") for p in values]
                    elif k == "name_part":
                        arg_group[k] = [regex.compile(p) for p in values]
                    elif k == "name_end":
                        arg_group[k] = [regex.compile(fr"{p}$") for p in values]
                    elif k == "extension":
                        arg_group[k] = [regex.compile(fr"^{p}$") for p in values]

            def get_key_pairs(arg_game_data):
                keys = dict()
                for key_name in get_value_tokens(arg_game_data.get("keylist") or ""):
                    key_fp = Path(arg_game_data.get("path"), "data", key_name).with_suffix(".key")
                    if key_fp.is_file():
                        keys[key_fp.stem] = key_fp
                return keys

            def get_filters(arg_filter_data):
                filters = {
                    "exclude_filenames": [],
                    "include_filenames": [],
                    "exclude_patterns": [],
                    "include_patterns": [],
                }
                for t_in, t_out in [("match", "include"), ("exclude", "exclude")]:
                    for entry in arg_filter_data.get(t_in) or []:
                        for name in get_value_tokens(entry.pop("fullname", "") or ""):
                            filters[f"{t_out}_filenames"].append(name)
                        if entry:
                            group = {k: get_value_tokens(v) for k, v in entry.items()}
                            compile_patterns(group)
                            filters[f"{t_out}_patterns"].append(group)
                return filters

            recipe_id, game_data, filter_data = self._data
            return {
                "id": recipe_id,
                "keys": get_key_pairs(game_data),
                "filters": get_filters(filter_data)
            }


class App:
    """
    Main application interface exposing curated subsets of functionality
    from core resource and file handling modules.

    Structure:
    - keybif:
        Handles game resource extraction related to KEY/BIF files.
        Methods:
            - export_game_resources
            - write_default_recipes
    - erf:
        Handles ERF archive processing with separate namespaces for batch
        and single-file operations.
        - erf.batch:
            Batch processing methods for ERF archives.
            Methods:
                - extract_erf_to_folder
                - create_erf_from_folder
        - erf.single:
            Single ERF archive processing methods.
            Methods:
                - extract_erf_to_folder
                - create_erf_from_folder
    - gff:
        Handles GFF (Generic File Format) processing and conversion,
        similarly split between batch and single file operations.
        - gff.batch:
            Batch conversion and serialization between GFF, JSON, and NDUGFF formats.
            Methods:
                - convert_gff_to_json
                - convert_json_to_gff
                - convert_gff_to_ndugff
                - convert_ndugff_to_gff
                - convert_json_to_ndugff
                - convert_ndugff_to_json
        - gff.single:
            Single file loading and writing for GFF, JSON, and NDUGFF formats.
            Methods:
                - load_gff
                - load_json
                - load_ndugff
                - write_gff
                - write_json
                - write_ndugff
        - gff.tools:
            Utility methods focused on file validation for GFF-related files.
            Methods:
                - is_gff_file
                - is_ndugff_file
                - is_json_file
                - is_erf_file
                - is_erf_folder
    """

    def __init__(self):
        def expose(arg_target, arg_source, arg_methods):
            for name in arg_methods:
                setattr(arg_target, name, getattr(arg_source, name))

        self.keybif = SimpleNamespace()
        expose(self.keybif, _KeyBif(), [
            "export_game_resources",
            "write_default_recipes",
        ])
        self.erf = SimpleNamespace()
        self.erf.batch = SimpleNamespace()
        expose(self.erf.batch, _Erf._Batch(), [
            "extract_erf_to_folder",
            "create_erf_from_folder",
        ])
        self.erf.single = SimpleNamespace()
        expose(self.erf.single, _Erf._Single(), [
            "extract_erf_to_folder",
            "create_erf_from_folder",
        ])
        self.gff = SimpleNamespace()
        self.gff.batch = SimpleNamespace()
        expose(self.gff.batch, _Gff._Batch(), [
            "convert_gff_to_json",
            "convert_json_to_gff",
            "convert_gff_to_ndugff",
            "convert_ndugff_to_gff",
            "convert_json_to_ndugff",
            "convert_ndugff_to_json",
        ])
        self.gff.single = SimpleNamespace()
        expose(self.gff.single, _Gff._Single(), [
            "load_gff",
            "load_json",
            "load_ndugff",
            "write_gff",
            "write_json",
            "write_ndugff",
        ])
        self.gff.tools = SimpleNamespace()
        expose(self.gff.tools, _Paths, [
            "is_gff_file",
            "is_ndugff_file",
            "is_json_file",
            "is_erf_file",
            "is_erf_folder",
        ])

    @staticmethod
    @contextmanager
    def log():
        """
        Context manager that redirects stdout and stderr to a log file.

        The log file is created in the same directory as the running script or executable.
        If that location cannot be determined or is not writable, it falls back to the user's desktop.

        Usage example:
            with App.log():
                print("This output will be captured in the log file.")
        """
        log_fp = _Paths._get_log_fp()
        with log_fp.open("w", encoding="utf-8") as f:
            default_stdout = sys.stdout
            default_stderr = sys.stderr
            sys.stdout = f
            sys.stderr = f
            try:
                yield
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                sys.stdout = default_stdout
                sys.stderr = default_stderr
